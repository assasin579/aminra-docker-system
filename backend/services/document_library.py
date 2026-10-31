"""Library selection is separate from upload chronology, approvals and CB packets."""
from __future__ import annotations

import json
from uuid import UUID
from fastapi import HTTPException
from services.document_versioning import MAX_CHAIN_DEPTH


# Same ordering as the library's latest_by_type view; null types stay per-file.
TYPE_REPRESENTATIVE_SQL = """
    SELECT d.id, cv.selected_at
    FROM documents d
    LEFT JOIN document_current_versions cv
      ON cv.current_document_id=d.id AND cv.tenant_id=d.tenant_id
    WHERE d.tenant_id=$1 AND d.doc_type IS NOT DISTINCT FROM $2::text
      AND (d.doc_type IS NOT NULL OR d.id=$3::uuid)
    ORDER BY cv.selected_at DESC NULLS LAST, d.uploaded_at DESC, d.id
    LIMIT 1
"""


async def select_current_version(db, *, tenant_id, document_id, actor_id):
    tenant_id, document_id, actor_id = UUID(str(tenant_id)), UUID(str(document_id)), UUID(str(actor_id))
    async with db.transaction():
        target = await db.fetchrow(
            "SELECT doc_type FROM documents WHERE id=$1 AND tenant_id=$2", document_id, tenant_id,
        )
        if not target:
            raise HTTPException(404, "Tài liệu hoặc chuỗi phiên bản không tồn tại")
        # Independent chains of one type share one representative. Serialize
        # switches across those chains, not just updates to a single chain row.
        await db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
            f"document-current-type:{tenant_id}:{target['doc_type'] or document_id}",
        )
        representative = await db.fetchrow(TYPE_REPRESENTATIVE_SQL, tenant_id, target['doc_type'], document_id)
        ancestry = []
        cursor = document_id
        for _ in range(MAX_CHAIN_DEPTH + 1):
            if cursor in ancestry:
                raise HTTPException(409, "Chuỗi phiên bản có vòng lặp")
            row = await db.fetchrow(
                "SELECT id, version_parent_id, approval_status, superseded_by_id FROM documents WHERE id=$1 AND tenant_id=$2",
                cursor, tenant_id,
            )
            if not row:
                raise HTTPException(404, "Tài liệu hoặc chuỗi phiên bản không tồn tại")
            if not ancestry and (row["approval_status"] == "obsolete" or row["superseded_by_id"]):
                raise HTTPException(409, "Phiên bản đã thay thế chỉ được xem trong lịch sử")
            ancestry.append(cursor)
            if not row["version_parent_id"]:
                break
            cursor = row["version_parent_id"]
        else:
            raise HTTPException(409, "Chuỗi phiên bản vượt giới hạn an toàn")
        # Lock in stable ID order, then ensure lineage did not change while loading.
        locked = await db.fetch(
            "SELECT id, version_parent_id, approval_status, superseded_by_id FROM documents WHERE tenant_id=$1 AND id=ANY($2::uuid[]) ORDER BY id FOR SHARE",
            tenant_id, ancestry,
        )
        selected = next((r for r in locked if r["id"] == document_id), None)
        if not selected or selected["approval_status"] == "obsolete" or selected["superseded_by_id"]:
            raise HTTPException(409, "Phiên bản đã thay thế hoặc vừa thay đổi")
        parents = {r["id"]: r["version_parent_id"] for r in locked}
        if len(locked) != len(ancestry) or any(parents.get(doc) != (ancestry[i + 1] if i + 1 < len(ancestry) else None) for i, doc in enumerate(ancestry)):
            raise HTTPException(409, "Chuỗi phiên bản vừa thay đổi; hãy tải lại và thử lại")
        root = ancestry[-1]
        changed = await db.fetchrow(
            """INSERT INTO document_current_versions (tenant_id,root_document_id,current_document_id,selected_by,selected_at)
               VALUES ($1,$2,$3,$4,GREATEST(clock_timestamp(),
                   COALESCE($6::timestamptz + interval '1 microsecond','-infinity'::timestamptz)))
               ON CONFLICT (tenant_id,root_document_id) DO UPDATE
               SET current_document_id=EXCLUDED.current_document_id,
                   selected_by=EXCLUDED.selected_by, selected_at=EXCLUDED.selected_at
               WHERE document_current_versions.current_document_id IS DISTINCT FROM EXCLUDED.current_document_id OR $5::boolean
               RETURNING selected_at""",
            tenant_id, root, document_id, actor_id,
            representative is None or representative['id'] != document_id,
            representative['selected_at'] if representative else None,
        )
        if changed:
            await db.execute(
                """INSERT INTO audit_logs (tenant_id,user_id,action,entity_type,entity_id,metadata)
                   VALUES ($1,$2,'document.current_version_selected','document',$3,$4::jsonb)""",
                tenant_id, actor_id, document_id, json.dumps({"root_document_id": str(root)}),
            )
    return {"message": "Đã chọn bản hiện hành trong chuỗi tài liệu; trạng thái phê duyệt không đổi",
            "document_id": str(document_id), "root_document_id": str(root), "changed": bool(changed)}
