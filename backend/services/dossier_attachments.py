"""Dossier-aware document reference associations.

A document row is a reusable immutable file/version identity; the relationship
with a Dossier is stored separately and is always checked against the Dossier's
server-pinned published requirements version.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException


async def validate_dossier_slot(db, *, dossier_id: UUID, tenant_id: UUID, doc_type: str) -> dict[str, Any]:
    dossier = await db.fetchrow(
        """SELECT d.id, d.tenant_id, d.requirements_version_id,
                  d.requirements_binding_status, d.status,
                  rv.state AS requirements_state
           FROM dossiers d
           LEFT JOIN standard_requirement_versions rv ON rv.id=d.requirements_version_id
           WHERE d.id=$1 AND d.tenant_id=$2
           FOR UPDATE OF d""",
        dossier_id,
        tenant_id,
    )
    if not dossier or dossier.get("status") == "cancelled":
        raise HTTPException(404, "Dossier không tồn tại hoặc không thuộc doanh nghiệp này")
    if dossier.get("requirements_binding_status") != "bound" or not dossier.get("requirements_version_id"):
        raise HTTPException(409, "Dossier chưa được gắn với phiên bản yêu cầu đã xác minh; không thể đính kèm tài liệu")
    if dossier.get("requirements_state") != "published":
        raise HTTPException(409, "Phiên bản yêu cầu của hồ sơ không còn hợp lệ")
    slot = await db.fetchrow(
        """SELECT doc_type FROM standard_requirement_version_slots
           WHERE requirements_version_id=$1 AND doc_type=$2""",
        dossier["requirements_version_id"],
        doc_type,
    )
    if not slot:
        raise HTTPException(422, "Loại tài liệu không thuộc phiên bản yêu cầu đã ghim cho hồ sơ")
    return dossier


async def find_idempotent_attachment(
    db, *, dossier: dict[str, Any], idempotency_key: UUID, request_sha256: str,
    doc_type: str, actor_id: UUID,
) -> dict[str, Any] | None:
    prior = await db.fetchrow(
        """SELECT a.document_id, a.doc_type, a.requirements_version_id, a.request_sha256,
                  a.attached_by, d.id, d.tenant_id, d.filename, d.original_filename, d.status,
                  d.compliance_score, d.version_number, d.uploaded_at
           FROM dossier_document_attachments a
           JOIN documents d ON d.id=a.document_id
           WHERE a.dossier_id=$1 AND a.idempotency_key=$2""",
        dossier["id"], idempotency_key,
    )
    if not prior:
        return None
    if (prior["doc_type"] != doc_type
        or str(prior["requirements_version_id"]) != str(dossier["requirements_version_id"])
        or str(prior.get("attached_by")) != str(actor_id)
        or prior["request_sha256"].strip() != request_sha256):
        raise HTTPException(409, "Idempotency key was already used for a different attachment request")
    document = {key: prior[key] for key in (
        "id", "tenant_id", "doc_type", "filename", "original_filename", "status",
        "compliance_score", "version_number", "uploaded_at",
    )}
    return {"document": document, "association": prior, "created": False}


async def attach_document_reference(
    db,
    *,
    dossier: dict[str, Any],
    document_id: UUID,
    doc_type: str,
    actor_id: UUID | None,
    idempotency_key: UUID,
    request_sha256: str,
) -> dict[str, Any]:
    prior = await find_idempotent_attachment(
        db, dossier=dossier, idempotency_key=idempotency_key,
        request_sha256=request_sha256, doc_type=doc_type, actor_id=actor_id,
    )
    if prior:
        return prior
    if len(request_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in request_sha256):
        raise HTTPException(422, "Invalid request fingerprint")
    document = await db.fetchrow(
        """SELECT id, tenant_id, doc_type, filename, original_filename,
                  status, compliance_score, version_number, uploaded_at
           FROM documents WHERE id=$1 AND tenant_id=$2""",
        document_id,
        dossier["tenant_id"],
    )
    if not document or str(document.get("tenant_id")) != str(dossier["tenant_id"]):
        raise HTTPException(404, "Tài liệu không tồn tại trong doanh nghiệp này")
    if document.get("doc_type") != doc_type:
        raise HTTPException(409, "Loại tài liệu không khớp với slot đã chọn")
    inserted = await db.fetchrow(
        """INSERT INTO dossier_document_attachments
                  (dossier_id, document_id, requirements_version_id, doc_type, attached_by,
                   idempotency_key, request_sha256)
           VALUES ($1,$2,$3,$4,$5,$6,$7)
           ON CONFLICT DO NOTHING
           RETURNING dossier_id, document_id, doc_type, requirements_version_id, attached_at""",
        dossier["id"],
        document["id"],
        dossier["requirements_version_id"],
        doc_type,
        actor_id,
        idempotency_key,
        request_sha256,
    )
    association = await db.fetchrow(
        """SELECT dossier_id, document_id, doc_type, requirements_version_id, attached_at
           FROM dossier_document_attachments
           WHERE dossier_id=$1 AND document_id=$2
             AND requirements_version_id=$3 AND doc_type=$4""",
        dossier["id"], document["id"], dossier["requirements_version_id"], doc_type,
    )
    if not association:
        raise HTTPException(409, "Không thể xác nhận liên kết tài liệu với hồ sơ")
    return {"document": document, "association": association, "created": inserted is not None}


async def list_dossier_documents(db, *, dossier_id: UUID) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """SELECT DISTINCT ON (d.id)
                  d.id, d.doc_type, d.filename, d.original_filename, d.status,
                  d.compliance_score, COALESCE(a.document_version_number, d.version_number) AS version_number, d.uploaded_at
           FROM dossiers ds
           LEFT JOIN dossier_document_attachments a
             ON a.dossier_id=ds.id AND a.requirements_version_id=ds.requirements_version_id
           LEFT JOIN documents d
             ON d.id=a.document_id
             OR (ds.requirements_binding_status <> 'bound' AND d.dossier_id=ds.id)
           WHERE ds.id=$1 AND d.id IS NOT NULL
           ORDER BY d.id, d.uploaded_at DESC""",
        dossier_id,
    )
    return [dict(row) for row in rows]


async def list_attachable_documents(db, *, dossier_id: UUID, tenant_id: UUID, requirements_version_id: UUID) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """SELECT d.id, d.doc_type, d.filename, d.original_filename, d.status,
                  d.version_number, d.uploaded_at
           FROM documents d
           JOIN standard_requirement_version_slots s
             ON s.requirements_version_id=$3 AND s.doc_type=d.doc_type
           WHERE d.tenant_id=$2
             AND d.file_path IS NOT NULL AND d.file_size IS NOT NULL
             AND (d.superseded_by_id IS NULL)
             AND NOT EXISTS (
                 SELECT 1 FROM dossier_document_attachments a
                 WHERE a.dossier_id=$1 AND a.document_id=d.id
             )
             AND d.dossier_id IS DISTINCT FROM $1
           ORDER BY d.uploaded_at DESC, d.id""",
        dossier_id, tenant_id, requirements_version_id,
    )
    return [dict(row) for row in rows]
