from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from services.dossier_readiness import compute_dossier_readiness


async def build_dashboard(db: Any, tenant_id: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Read a tenant dashboard under one PostgreSQL repeatable-read snapshot."""
    if page < 1 or page_size < 1 or page_size > 50:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid pagination")
    async with db.transaction(isolation="repeatable_read", readonly=True):
        as_of = await db.fetchval("SELECT transaction_timestamp()")
        count = await db.fetchval(
            "SELECT count(*) FROM dossiers WHERE tenant_id = $1 AND status != 'cancelled'",
            tenant_id,
        )
        rows = await db.fetch(
            """SELECT id, tenant_id, standard_type_id, requirements_version_id,
                      requirements_binding_status, title, status, updated_at
                 FROM dossiers WHERE tenant_id = $1 AND status != 'cancelled'
                ORDER BY updated_at DESC, id ASC OFFSET $2 LIMIT $3""",
            tenant_id, (page - 1) * page_size, page_size,
        )
        profiles: dict[str, dict[str, Any]] = {}
        for row in rows:
            standard_id = row.get("standard_type_id")
            if standard_id is None:
                key = "unknown"
                profile = profiles.setdefault(key, {"id": None, "code": None, "name_vi": None, "dossiers": []})
            else:
                standard = await db.fetchrow(
                    "SELECT id, code, name_vi FROM standard_types WHERE id = $1", standard_id
                )
                key = str(standard["id"]) if standard else "unknown"
                profile = profiles.setdefault(key, {
                    "id": str(standard["id"]) if standard else None,
                    "code": standard["code"] if standard else None,
                    "name_vi": standard["name_vi"] if standard else None,
                    "dossiers": [],
                })
            readiness = await compute_dossier_readiness(db, dossier_id=str(row["id"]), tenant_id=str(tenant_id))
            profile["dossiers"].append({
                "id": str(row["id"]), "title": row["title"], "status": row["status"],
                "requirements_version_id": str(row["requirements_version_id"]) if row.get("requirements_version_id") else None,
                "requirements_binding_status": row.get("requirements_binding_status") or "unknown",
                "updated_at": row["updated_at"].isoformat(), "readiness": readiness,
            })
        if as_of is None:
            raise RuntimeError("Database transaction snapshot timestamp unavailable")
        stamp = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)
        return {"schema_version": "1.0", "state": "first_use" if count == 0 else "ready",
                "as_of": stamp, "page": page, "page_size": page_size, "total_dossiers": count,
                "profiles": list(profiles.values())}
