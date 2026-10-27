from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from auth.requirements_authorization import require_platform_admin_capability


def canonicalize_requirement_slots(rows) -> tuple[list[dict[str, Any]], str]:
    """Canonical JSON semantics: NFC-normalized doc_type, numeric ordering, explicit booleans."""
    import unicodedata
    normalized = [
        {
            "doc_type": unicodedata.normalize("NFC", str(r["doc_type"]).strip()),
            "required": r["required"] is True,
            "display_order": int(r["display_order"]),
        }
        for r in rows
    ]
    normalized.sort(key=lambda slot: (slot["display_order"], slot["doc_type"]))
    keys = [slot["doc_type"] for slot in normalized]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise HTTPException(status.HTTP_409_CONFLICT, "Requirement slots contain duplicate or empty doc_type")
    canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return normalized, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def publish_requirements_version(db, *, standard_type_id: UUID, actor: dict, actor_id: UUID | None) -> dict[str, Any]:
    """Snapshot canonical Admin-managed slots and atomically publish an immutable version."""
    require_platform_admin_capability(actor)
    if actor_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Canonical platform admin identity is required")
    async with db.transaction():
        standard = await db.fetchrow("SELECT id FROM standard_types WHERE id = $1 FOR UPDATE", standard_type_id)
        if not standard:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Standard not found")
        slots = await db.fetch(
            "SELECT doc_type, required, display_order FROM standard_doc_types WHERE standard_type_id = $1 ORDER BY display_order, doc_type",
            standard_type_id,
        )
        payload, digest = canonicalize_requirement_slots(slots)
        current = await db.fetchrow(
            "SELECT v.id, v.version_number, v.content_sha256 FROM standard_requirement_current_versions c JOIN standard_requirement_versions v ON v.id=c.requirements_version_id WHERE c.standard_type_id=$1",
            standard_type_id,
        )
        if current and current["content_sha256"].strip() == digest:
            return {"requirements_version_id": str(current["id"]), "version_number": current["version_number"], "content_sha256": digest, "unchanged": True}
        version_number = await db.fetchval("SELECT COALESCE(MAX(version_number), 0) + 1 FROM standard_requirement_versions WHERE standard_type_id=$1", standard_type_id)
        version = await db.fetchrow(
            "INSERT INTO standard_requirement_versions (standard_type_id, version_number, state, content_sha256, created_by) VALUES ($1, $2, 'draft', $3, $4) RETURNING id",
            standard_type_id, version_number, digest, actor_id,
        )
        version_id = version["id"]
        for slot in payload:
            await db.execute(
                "INSERT INTO standard_requirement_version_slots (requirements_version_id, standard_type_id, doc_type, required, display_order) VALUES ($1, $2, $3, $4, $5)",
                version_id, standard_type_id, slot["doc_type"], slot["required"], slot["display_order"],
            )
        await db.execute("UPDATE standard_requirement_versions SET state='published', published_by=$2, published_at=NOW() WHERE id=$1", version_id, actor_id)
        await db.execute(
            "INSERT INTO standard_requirement_current_versions (standard_type_id, requirements_version_id) VALUES ($1, $2) ON CONFLICT (standard_type_id) DO UPDATE SET requirements_version_id=EXCLUDED.requirements_version_id, updated_at=NOW()",
            standard_type_id, version_id,
        )
        await db.execute(
            "INSERT INTO audit_logs (user_id, user_email, user_role, action, entity_type, entity_id, changes, metadata) VALUES ($1, $2, $3, 'requirements_version_published', 'standard_type', $4, $5::jsonb, $6::jsonb)",
            actor_id, actor.get("email"), actor.get("role"), standard_type_id,
            json.dumps({"requirements_version_id": str(version_id), "version_number": version_number}),
            json.dumps({"content_sha256": digest, "slot_count": len(payload), "capability": "platform_admin"}),
        )
        return {"requirements_version_id": str(version_id), "version_number": version_number, "content_sha256": digest, "unchanged": False}
