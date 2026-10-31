"""Dossiers (hồ sơ) — instance of a doc collection theo 1 standard.

Mỗi hồ sơ:
  - Thuộc 1 tenant
  - Chọn 1 standard_type → quyết định doc_types nào cần
  - Có status lifecycle: draft → in_progress → submitted → cert_issued

Endpoints:
  GET    /dossiers              — list of current tenant's dossiers
  POST   /dossiers              — create new dossier (title + standard_type)
  GET    /dossiers/{id}         — detail + doc_types from standard + status
  PATCH  /dossiers/{id}         — update title/status/notes
  DELETE /dossiers/{id}         — soft delete (status='cancelled')
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import Response, APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.identity import resolve_canonical_user_id
from auth.permissions import check_permission_db
from auth.upload_utils import validate_upload
from services.dossier_attachments import (
    attach_document_reference,
    find_idempotent_attachment,
    list_attachable_documents,
    list_dossier_documents,
    validate_dossier_slot,
)
from services.dossier_readiness import compute_dossier_readiness

log = logging.getLogger("aminra.dossier")

router = APIRouter()


# ── Pydantic ────────────────────────────────────────────────────────────────


class DocTypeRequirement(BaseModel):
    doc_type: str
    required: bool
    display_order: int


class DocumentInDossier(BaseModel):
    id: str
    doc_type: Optional[str] = None
    filename: str
    original_filename: str
    status: Optional[str] = None
    compliance_score: Optional[int] = None
    version_number: int = 1
    uploaded_at: str


class DossierPublic(BaseModel):
    id: str
    tenant_id: str
    standard_type_id: Optional[str] = None
    standard_code: Optional[str] = None
    standard_name_vi: Optional[str] = None
    requirements_version_id: Optional[str] = None
    requirements_binding_status: str = "unknown"
    title: str
    status: str
    notes: Optional[str] = None
    doc_types: List[DocTypeRequirement] = []
    documents: List[DocumentInDossier] = []
    created_at: str
    updated_at: str


class DossierCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    standard_type_id: UUID
    notes: Optional[str] = None


class DossierUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(
        None, pattern=r"^(draft|in_progress|submitted|cert_issued|cancelled)$"
    )
    notes: Optional[str] = None


class DossierReadinessItemResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    code: Optional[str] = None
    title: Optional[str] = None
    label: Optional[str] = None
    doc_type: Optional[str] = None
    document_id: Optional[str] = None
    filename: Optional[str] = None
    reason: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None


class DossierReadinessResponse(BaseModel):
    dossier_id: str
    tenant_id: str
    status: Optional[str] = None
    title: Optional[str] = None
    requirements_version_id: Optional[str] = None
    requirements_binding_status: str = "unknown"
    state: str
    readiness_percent: Optional[int] = Field(default=None, strict=True, ge=0, le=100)
    certificate_issue_blocked: bool = Field(strict=True)
    safe_public_trace_available: bool = Field(strict=True)
    next_action: Optional[str] = None
    next_actor_role: Optional[str] = None
    next_action_owner_role: Optional[str] = None
    due_date: Optional[str] = None
    required_documents: list[str | DossierReadinessItemResponse]
    requirement_slots: list[DossierReadinessItemResponse] = Field(default_factory=list)
    missing_required_documents: list[str | DossierReadinessItemResponse]
    unreviewed_documents: list[DossierReadinessItemResponse]
    rejected_documents: list[DossierReadinessItemResponse]
    open_ncrs: list[DossierReadinessItemResponse]
    blocking_ncrs: list[DossierReadinessItemResponse]
    certification_decision: dict[str, Any] | None
    submission_round: dict[str, Any] | None = None
    certificate: dict[str, Any] | None
    blocking_reasons: list[str | DossierReadinessItemResponse]


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _resolve_tenant_id(db, user: dict) -> Optional[UUID]:
    """Resolve canonical tenant_id (DB UUID, not Keycloak slug). Thin shim
    over the shared helper so existing call sites stay readable."""
    from .identity import resolve_canonical_tenant_id
    return await resolve_canonical_tenant_id(user, db)


async def _row_to_public(db, row, include_documents: bool = False) -> DossierPublic:
    standard_info = None
    doc_types: List[DocTypeRequirement] = []
    if row["standard_type_id"]:
        standard_info = await db.fetchrow(
            "SELECT code, name_vi FROM standard_types WHERE id = $1",
            row["standard_type_id"],
        )
        binding_status = row.get("requirements_binding_status") or "unknown"
        version_id = row.get("requirements_version_id")
        if binding_status == "bound" and version_id:
            dt_rows = await db.fetch(
                "SELECT doc_type, required, display_order FROM standard_requirement_version_slots "
                "WHERE requirements_version_id = $1 ORDER BY display_order, doc_type",
                version_id,
            )
            doc_types = [DocTypeRequirement(**dict(r)) for r in dt_rows]

    documents: List[DocumentInDossier] = []
    if include_documents:
        doc_rows = await list_dossier_documents(db, dossier_id=row["id"])
        documents = [
            DocumentInDossier(
                id=str(r["id"]),
                doc_type=r["doc_type"],
                filename=r["filename"],
                original_filename=r["original_filename"],
                status=str(r["status"]) if r["status"] else None,
                compliance_score=r["compliance_score"],
                version_number=r["version_number"],
                uploaded_at=r["uploaded_at"].isoformat(),
            )
            for r in doc_rows
        ]

    return DossierPublic(
        id=str(row["id"]),
        tenant_id=str(row["tenant_id"]),
        standard_type_id=str(row["standard_type_id"]) if row["standard_type_id"] else None,
        standard_code=standard_info["code"] if standard_info else None,
        standard_name_vi=standard_info["name_vi"] if standard_info else None,
        requirements_version_id=str(row["requirements_version_id"]) if row.get("requirements_version_id") else None,
        requirements_binding_status=row.get("requirements_binding_status") or "unknown",
        title=row["title"],
        status=row["status"],
        notes=row.get("notes"),
        doc_types=doc_types,
        documents=documents,
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def get_dossier_dashboard(
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
    response: Response = None,
):
    if response is not None:
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Authorization"
    if user.get("role") != "business":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business users can read dossier dashboard")
    if page < 1 or page_size < 1 or page_size > 50:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid pagination")
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")
    from services.dossier_dashboard import build_dashboard
    return await build_dashboard(db, str(tenant_id), page, page_size)


@router.get("", response_model=List[DossierPublic])
async def list_dossiers(
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        return []
    rows = await db.fetch(
        "SELECT * FROM dossiers WHERE tenant_id = $1 AND status != 'cancelled' "
        "ORDER BY updated_at DESC",
        tenant_id,
    )
    return [await _row_to_public(db, r) for r in rows]


@router.post("", response_model=DossierPublic, status_code=201)
async def create_dossier(
    req: DossierCreate,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    if user.get("role") != "business":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business users can create dossiers")
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User row not found in DB. Call /auth/me first.")

    # Validate standard exists + enabled
    std = await db.fetchrow(
        "SELECT id, code FROM standard_types WHERE id = $1 AND enabled = true",
        req.standard_type_id,
    )
    if not std:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Standard not found or disabled")

    current_requirements = await db.fetchrow(
        "SELECT requirements_version_id FROM standard_requirement_current_versions WHERE standard_type_id = $1",
        req.standard_type_id,
    )
    requirements_version_id = current_requirements["requirements_version_id"] if current_requirements else None
    binding_status = "bound" if requirements_version_id else "unconfigured"

    # Optional sanity: warn if standard not in user's industry available list
    db_user = await db.fetchrow(
        "SELECT id, industry_schema_id FROM users WHERE email = $1", user["email"],
    )
    if db_user and db_user["industry_schema_id"]:
        ok = await db.fetchval(
            "SELECT 1 FROM industry_standards "
            "WHERE industry_schema_id = $1 AND standard_type_id = $2",
            db_user["industry_schema_id"], req.standard_type_id,
        )
        if not ok:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Standard không phải là tiêu chuẩn của ngành nghề bạn. "
                "Nếu cần áp dụng đa-tiêu-chuẩn, liên hệ admin.",
            )

    row = await db.fetchrow(
        """INSERT INTO dossiers (tenant_id, standard_type_id, requirements_version_id,
                               requirements_binding_status, title, status, notes, created_by)
           VALUES ($1, $2, $3, $4, $5, 'draft', $6, $7) RETURNING *""",
        tenant_id, req.standard_type_id, requirements_version_id, binding_status,
        req.title, req.notes, db_user["id"] if db_user else None,
    )
    log.info("[dossier] tenant %s created '%s' (standard %s)",
             tenant_id, req.title, std["code"])

    await db.execute(
        "INSERT INTO audit_logs (user_id, tenant_id, action, entity_type, entity_id, metadata) "
        "VALUES ($1, $2, 'dossier_created', 'dossier', $3, $4::jsonb)",
        db_user["id"] if db_user else None, tenant_id, row["id"],
        f'{{"title":"{req.title}","standard_code":"{std["code"]}"}}',
    )
    return await _row_to_public(db, row)


@router.get("/{dossier_id}/readiness", response_model=DossierReadinessResponse)
async def get_dossier_readiness(
    dossier_id: UUID,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
    response: Response = None,
):
    if response is not None:
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Authorization"
    if user.get("role") != "business":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business users can read dossier readiness")
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")
    return await compute_dossier_readiness(
        db,
        dossier_id=str(dossier_id),
        tenant_id=str(tenant_id),
    )


@router.get("/{dossier_id}/attachable-documents")
async def get_attachable_documents(
    dossier_id: UUID,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    if user.get("role") != "business":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business users can attach documents")
    await check_permission_db(user, "can_upload")
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")
    dossier = await db.fetchrow(
        """SELECT d.id, d.requirements_version_id, d.requirements_binding_status,
                  d.status, rv.state AS requirements_state
           FROM dossiers d LEFT JOIN standard_requirement_versions rv
             ON rv.id=d.requirements_version_id
           WHERE d.id=$1 AND d.tenant_id=$2""",
        dossier_id, tenant_id,
    )
    if not dossier or dossier.get("status") == "cancelled":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier not found")
    if dossier.get("requirements_binding_status") != "bound" or not dossier.get("requirements_version_id"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Dossier chưa được gắn với phiên bản yêu cầu đã xác minh")
    if dossier.get("requirements_state") != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Phiên bản yêu cầu của hồ sơ không còn hợp lệ")
    rows = await list_attachable_documents(
        db, dossier_id=dossier_id, tenant_id=tenant_id,
        requirements_version_id=dossier["requirements_version_id"],
    )
    return {"items": [{**row, "id": str(row["id"])} for row in rows]}


@router.post("/{dossier_id}/documents")
async def attach_or_upload_dossier_document(
    dossier_id: UUID,
    doc_type: str = Form(...),
    document_id: UUID | None = Form(None),
    file: UploadFile | None = File(None),
    idempotency_key: UUID = Header(..., alias="Idempotency-Key"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    if user.get("role") != "business":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business users can attach documents")
    await check_permission_db(user, "can_upload")
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")
    actor_id = await resolve_canonical_user_id(user, db)
    if not actor_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Không xác định được danh tính người thao tác")
    doc_type = doc_type.strip()
    if not doc_type or len(doc_type) > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Slot tài liệu không hợp lệ")
    if (document_id is None) == (file is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Chọn đúng một tài liệu có sẵn hoặc tệp mới")

    saved_path: Path | None = None
    try:
        async with db.transaction():
            dossier = await validate_dossier_slot(
                db, dossier_id=dossier_id, tenant_id=tenant_id, doc_type=doc_type,
            )
            content: bytes | None = None
            safe_name = ""
            mime_type = "application/octet-stream"
            if file is not None:
                content = await validate_upload(file)
                safe_name = "".join(
                    char if char.isalnum() or char in "._- " else "_"
                    for char in (file.filename or "file")
                ).strip() or "file"
                mime_type = file.content_type or mime_type
                content_digest = hashlib.sha256(content).hexdigest()
            else:
                content_digest = str(document_id)

            fingerprint_payload = {
                "action": "dossier-document-attachment-v1",
                "actor_id": str(actor_id),
                "tenant_id": str(tenant_id),
                "dossier_id": str(dossier_id),
                "requirements_version_id": str(dossier["requirements_version_id"]),
                "doc_type": doc_type,
                "document_id": str(document_id) if document_id else None,
                "content_sha256": content_digest,
                "filename": safe_name if file is not None else None,
                "mime_type": mime_type if file is not None else None,
            }
            request_sha256 = hashlib.sha256(
                json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            result = await find_idempotent_attachment(
                db, dossier=dossier, idempotency_key=idempotency_key,
                request_sha256=request_sha256, doc_type=doc_type, actor_id=actor_id,
            )
            if result is None and document_id is not None:
                result = await attach_document_reference(
                    db, dossier=dossier, document_id=document_id,
                    doc_type=doc_type, actor_id=actor_id,
                    idempotency_key=idempotency_key, request_sha256=request_sha256,
                )
            elif result is None:
                if file is None or content is None:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tệp tải lên không có")
                from auth.document_router import UPLOAD_DIR
                tenant_dir = UPLOAD_DIR / str(tenant_id)
                tenant_dir.mkdir(parents=True, exist_ok=True)
                doc_uuid = uuid4()
                saved_path = tenant_dir / f"{doc_uuid}_{safe_name}"
                if not saved_path.resolve().is_relative_to(tenant_dir.resolve()):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file path")
                saved_path.write_bytes(content)
                inserted = await db.fetchrow(
                    """INSERT INTO documents
                              (id, filename, original_filename, file_path, file_size, mime_type,
                               user_id, tenant_id, doc_type)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                       RETURNING id, tenant_id, doc_type, filename, original_filename,
                                 status, compliance_score, version_number, uploaded_at""",
                    doc_uuid, saved_path.name, file.filename or safe_name, str(saved_path),
                    len(content), mime_type, actor_id, tenant_id, doc_type,
                )
                if not inserted:
                    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể lưu metadata tài liệu")
                result = await attach_document_reference(
                    db, dossier=dossier, document_id=doc_uuid,
                    doc_type=doc_type, actor_id=actor_id,
                    idempotency_key=idempotency_key, request_sha256=request_sha256,
                )
        document = result["document"]
        return {
            "document_id": str(document["id"]),
            "doc_type": document["doc_type"],
            "attachment_state": "attached",
            "created_attachment": result["created"],
        }
    except Exception:
        if saved_path is not None:
            try:
                if saved_path.exists():
                    saved_path.unlink()
            except OSError:
                log.exception("Failed to remove uncommitted Dossier attachment file")
        raise


@router.get("/{dossier_id}", response_model=DossierPublic)
async def get_dossier(
    dossier_id: UUID,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")
    row = await db.fetchrow(
        "SELECT * FROM dossiers WHERE id = $1 AND tenant_id = $2",
        dossier_id, tenant_id,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier not found")
    return await _row_to_public(db, row, include_documents=True)


@router.patch("/{dossier_id}", response_model=DossierPublic)
async def update_dossier(
    dossier_id: UUID,
    req: DossierUpdate,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")

    sets, params, idx = [], [], 1
    for field, val in req.model_dump(exclude_unset=True).items():
        sets.append(f"{field} = ${idx}")
        params.append(val)
        idx += 1
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    sets.append("updated_at = NOW()")
    params.extend([dossier_id, tenant_id])
    row = await db.fetchrow(
        f"UPDATE dossiers SET {', '.join(sets)} "
        f"WHERE id = ${idx} AND tenant_id = ${idx+1} RETURNING *",
        *params,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier not found")
    return await _row_to_public(db, row)


@router.delete("/{dossier_id}", status_code=204)
async def delete_dossier(
    dossier_id: UUID,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    tenant_id = await _resolve_tenant_id(db, user)
    if not tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not resolvable")
    await db.execute(
        "UPDATE dossiers SET status = 'cancelled', updated_at = NOW() "
        "WHERE id = $1 AND tenant_id = $2",
        dossier_id, tenant_id,
    )
