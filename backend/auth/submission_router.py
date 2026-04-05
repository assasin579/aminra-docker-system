"""
Submission API — Business sends document packages to Providers for review.
"""
import logging
from typing import Optional, List
from datetime import datetime

from uuid import UUID as _UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from asyncpg import Connection

from auth.db import get_db
from auth.jwt_utils import get_current_user, require_business_owner


def _validate_uuid(value: str) -> str:
    try:
        _UUID(value)
    except ValueError:
        raise HTTPException(400, "Invalid ID format")
    return value

log = logging.getLogger("aminra.submissions")
router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    provider_id: str
    document_ids: List[str]
    notes: str = ""


class UpdateStatusRequest(BaseModel):
    status: str       # reviewing, returned, approved
    auditor_notes: str = ""


class AssignAuditorRequest(BaseModel):
    auditor_id: str


# ── Business: list providers ──────────────────────────────────────────────────

@router.get("/providers")
async def list_providers(db: Connection = Depends(get_db)):
    """List active provider organizations (owners only, not auditors)."""
    rows = await db.fetch(
        "SELECT id, company_name, email, status FROM users WHERE role = 'provider' AND status = 'active' AND is_owner = true ORDER BY company_name"
    )
    return {"providers": [
        {"id": str(r["id"]), "company_name": r["company_name"], "email": r["email"]}
        for r in rows
    ]}


# ── Business: submit documents ────────────────────────────────────────────────

@router.post("/submit")
async def submit_documents(
    req: SubmitRequest,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Business sends selected documents to a provider."""
    tenant_id = owner["tenant_id"]

    # Verify provider is an organization owner (not an auditor)
    provider = await db.fetchrow(
        "SELECT id, company_name FROM users WHERE id = $1 AND role = 'provider' AND status = 'active' AND is_owner = true",
        req.provider_id,
    )
    if not provider:
        raise HTTPException(404, "Tổ chức chứng nhận không tồn tại hoặc chưa được duyệt")

    # Verify documents belong to tenant
    doc_uuids = [d for d in req.document_ids]
    if doc_uuids:
        count = await db.fetchval(
            "SELECT COUNT(*) FROM documents WHERE id = ANY($1::uuid[]) AND tenant_id = $2",
            doc_uuids, tenant_id,
        )
        if count != len(doc_uuids):
            raise HTTPException(400, "Một số tài liệu không hợp lệ")

    # Get business company name
    biz = await db.fetchrow("SELECT company_name FROM users WHERE id = $1", owner["sub"])
    company_name = biz["company_name"] if biz else ""

    row = await db.fetchrow(
        """INSERT INTO submissions (business_tenant, provider_id, document_ids, notes, company_name)
           VALUES ($1, $2, $3::uuid[], $4, $5) RETURNING id, submitted_at""",
        tenant_id, req.provider_id, doc_uuids, req.notes, company_name,
    )

    log.info(f"[submission] {company_name} → {provider['company_name']}: {len(doc_uuids)} docs")
    return {
        "submission_id": str(row["id"]),
        "submitted_at": row["submitted_at"].isoformat(),
        "message": f"Đã gửi {len(doc_uuids)} tài liệu đến {provider['company_name']}",
    }


# ── Business: list my submissions ─────────────────────────────────────────────

@router.get("/my-submissions")
async def my_submissions(
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    rows = await db.fetch(
        """SELECT s.id, s.status, s.notes, s.auditor_notes, s.submitted_at, s.updated_at,
                  array_length(s.document_ids, 1) AS doc_count,
                  p.company_name AS provider_name, p.email AS provider_email
           FROM submissions s
           JOIN users p ON p.id = s.provider_id
           WHERE s.business_tenant = $1
           ORDER BY s.submitted_at DESC""",
        owner["tenant_id"],
    )
    return {"submissions": [
        {
            "id": str(r["id"]), "status": r["status"],
            "notes": r["notes"], "auditor_notes": r["auditor_notes"],
            "doc_count": r["doc_count"] or 0,
            "provider_name": r["provider_name"], "provider_email": r["provider_email"],
            "submitted_at": r["submitted_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        } for r in rows
    ]}


# ── Provider: list received submissions ───────────────────────────────────────

@router.get("/received")
async def received_submissions(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    if user["role"] != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")

    rows = await db.fetch(
        """SELECT s.id, s.business_tenant, s.status, s.notes, s.auditor_notes,
                  s.submitted_at, s.updated_at, s.company_name,
                  s.auditor_id, s.document_ids,
                  array_length(s.document_ids, 1) AS doc_count
           FROM submissions s
           WHERE s.provider_id = $1
           ORDER BY s.submitted_at DESC""",
        user["sub"],
    )

    result = []
    for r in rows:
        # Get auditor name if assigned
        auditor_name = None
        if r["auditor_id"]:
            ar = await db.fetchrow("SELECT company_name FROM users WHERE id = $1", r["auditor_id"])
            if ar: auditor_name = ar["company_name"]

        result.append({
            "id": str(r["id"]),
            "company_name": r["company_name"],
            "status": r["status"],
            "notes": r["notes"],
            "auditor_notes": r["auditor_notes"],
            "doc_count": r["doc_count"] or 0,
            "document_ids": [str(d) for d in (r["document_ids"] or [])],
            "auditor_id": str(r["auditor_id"]) if r["auditor_id"] else None,
            "auditor_name": auditor_name,
            "submitted_at": r["submitted_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        })

    return {"submissions": result}


# ── Provider: get documents in a submission ───────────────────────────────────

@router.get("/received/{submission_id}/documents")
async def submission_documents(
    submission_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    _validate_uuid(submission_id)
    if user["role"] != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")

    sub = await db.fetchrow(
        "SELECT document_ids FROM submissions WHERE id = $1 AND provider_id = $2",
        submission_id, user["sub"],
    )
    if not sub:
        raise HTTPException(404, "Không tìm thấy hồ sơ")

    doc_ids = sub["document_ids"] or []
    if not doc_ids:
        return {"documents": []}

    rows = await db.fetch(
        """SELECT id, original_filename, doc_type, compliance_score,
                  file_size, mime_type, uploaded_at, evaluation_result
           FROM documents WHERE id = ANY($1::uuid[])
           ORDER BY uploaded_at DESC""",
        doc_ids,
    )

    docs = []
    for r in rows:
        er = r["evaluation_result"]
        if isinstance(er, str):
            import json
            try: er = json.loads(er)
            except: er = {}
        elif er is None:
            er = {}
        docs.append({
            "id": str(r["id"]),
            "original_filename": r["original_filename"],
            "doc_type": r["doc_type"],
            "doc_type_label": er.get("doc_type_label"),
            "compliance_score": r["compliance_score"],
            "overall_status": er.get("overall_status"),
            "file_size": r["file_size"],
            "uploaded_at": r["uploaded_at"].isoformat(),
        })

    return {"documents": docs}


# ── Provider: update submission status ────────────────────────────────────────

@router.put("/received/{submission_id}/status")
async def update_submission_status(
    submission_id: str,
    req: UpdateStatusRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    _validate_uuid(submission_id)
    if user["role"] != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")

    if req.status not in ("reviewing", "returned", "approved"):
        raise HTTPException(400, "Status không hợp lệ")

    result = await db.execute(
        "UPDATE submissions SET status = $1, auditor_notes = $2, updated_at = NOW() WHERE id = $3 AND provider_id = $4",
        req.status, req.auditor_notes, submission_id, user["sub"],
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Không tìm thấy hồ sơ")

    log.info(f"[submission] {submission_id} → {req.status}")
    return {"message": f"Đã cập nhật trạng thái: {req.status}"}


# ── Provider: assign auditor ──────────────────────────────────────────────────

@router.put("/received/{submission_id}/assign")
async def assign_auditor(
    submission_id: str,
    req: AssignAuditorRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    _validate_uuid(submission_id)
    if user["role"] != "provider" or not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức mới được gán auditor")

    # Verify auditor belongs to this provider's team
    auditor = await db.fetchrow(
        "SELECT id FROM users WHERE id = $1 AND tenant_id = $2 AND is_owner = false AND role = 'provider'",
        req.auditor_id, user["sub"],
    )
    if not auditor:
        raise HTTPException(404, "Auditor không tồn tại trong tổ chức")

    result = await db.execute(
        "UPDATE submissions SET auditor_id = $1, status = 'reviewing', updated_at = NOW() WHERE id = $2 AND provider_id = $3",
        req.auditor_id, submission_id, user["sub"],
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Không tìm thấy hồ sơ")

    log.info(f"[submission] {submission_id} assigned to auditor {req.auditor_id}")
    return {"message": "Đã gán auditor"}
