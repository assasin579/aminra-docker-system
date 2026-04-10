"""
Submission API — Business sends document packages to Providers for review.
"""
import logging
import json as _json
from typing import Optional, List
from datetime import datetime

from uuid import UUID as _UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from asyncpg import Connection

from auth.db import get_db
from auth.jwt_utils import get_current_user, require_business_owner
from auth.notification_router import notify


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


# ── Helper: access filter for owner vs auditor ──────────────────────────────

def _provider_filter(user: dict, alias: str = "s"):
    """Return (where_clause, param) for owner vs auditor access."""
    col = "provider_id" if user.get("is_owner") else "auditor_id"
    prefix = f"{alias}." if alias else ""
    return f"{prefix}{col} = $1", user["sub"]


# ── CB Dashboard: comprehensive stats ────────────────────────────────────────

@router.get("/cb-stats")
async def cb_stats(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Comprehensive CB dashboard stats — owner only."""
    if user["role"] != "provider":
        raise HTTPException(403)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    pid = user.get("tenant_id") or user["sub"]

    # Portfolio size
    portfolio = await db.fetchval("""
        SELECT COUNT(DISTINCT business_tenant) FROM (
            SELECT business_tenant FROM submissions WHERE provider_id=$1
            UNION SELECT business_tenant FROM audit_visits WHERE provider_id=$1
        ) t
    """, pid)

    # Cert stats
    certs = await db.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='active') AS active,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date < NOW() + INTERVAL '90 days') AS expiring_soon,
            COUNT(*) FILTER (WHERE status='suspended' OR status='revoked') AS inactive
        FROM halal_certificates WHERE issued_by=$1
    """, pid)

    # Audit stats
    audits = await db.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status IN ('completed','report_submitted')) AS completed,
            ROUND(AVG(compliance_score) FILTER (WHERE compliance_score IS NOT NULL)) AS avg_compliance
        FROM audit_visits WHERE provider_id=$1
    """, pid)

    # Submission stats (reuse existing)
    subs = await db.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE status='pending') AS pending,
            COUNT(*) FILTER (WHERE status='reviewing') AS reviewing,
            COUNT(*) FILTER (WHERE status='approved') AS approved,
            COUNT(*) AS total,
            ROUND(EXTRACT(EPOCH FROM AVG(updated_at - submitted_at) FILTER (WHERE status != 'pending')) / 3600, 1) AS avg_hours
        FROM submissions WHERE provider_id=$1
    """, pid)

    # Auditor workload
    auditors = await db.fetch("""
        SELECT a.id, a.company_name,
            (SELECT COUNT(*) FROM audit_visits WHERE auditor_id=a.id AND status IN ('scheduled','in_progress')) AS active_visits,
            (SELECT COUNT(*) FROM submissions WHERE auditor_id=a.id AND status IN ('assigned','reviewing')) AS active_submissions
        FROM users a
        WHERE a.tenant_id=$1 AND a.is_owner=false AND a.role='provider' AND a.status='active'
    """, pid)

    # Expiring certs (next 90 days)
    expiring = await db.fetch("""
        SELECT cert_number, company_name, expiry_date
        FROM halal_certificates
        WHERE issued_by=$1 AND status='active' AND expiry_date < NOW() + INTERVAL '90 days'
        ORDER BY expiry_date ASC LIMIT 10
    """, pid)

    return {
        "portfolio_size": portfolio or 0,
        "certs": {
            "total": certs["total"], "active": certs["active"],
            "expiring_soon": certs["expiring_soon"], "inactive": certs["inactive"],
        },
        "audits": {
            "total": audits["total"], "completed": audits["completed"],
            "avg_compliance": int(audits["avg_compliance"]) if audits["avg_compliance"] else None,
        },
        "submissions": {
            "pending": subs["pending"], "reviewing": subs["reviewing"],
            "approved": subs["approved"], "total": subs["total"],
            "avg_hours": float(subs["avg_hours"]) if subs["avg_hours"] else None,
        },
        "auditor_workload": [
            {"id": str(a["id"]), "name": a["company_name"],
             "active_visits": a["active_visits"], "active_submissions": a["active_submissions"]}
            for a in auditors
        ],
        "expiring_certs": [
            {"cert_number": e["cert_number"], "company_name": e["company_name"],
             "expiry_date": e["expiry_date"].isoformat(),
             "days_remaining": (e["expiry_date"] - __import__('datetime').date.today()).days}
            for e in expiring
        ],
    }


# ── Provider: dashboard stats ────────────────────────────────────────────────

@router.get("/stats")
async def provider_stats(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    if user["role"] != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")

    where, param = _provider_filter(user)

    # Counts by status
    counts = await db.fetchrow(f"""
        SELECT
            COUNT(*) FILTER (WHERE s.status = 'pending')   AS pending,
            COUNT(*) FILTER (WHERE s.status = 'reviewing') AS reviewing,
            COUNT(*) FILTER (WHERE s.status = 'approved')  AS approved,
            COUNT(*) FILTER (WHERE s.status = 'returned')  AS returned,
            COUNT(*)                                        AS total,
            COUNT(*) FILTER (WHERE s.deadline IS NOT NULL AND s.deadline < NOW() AND s.status NOT IN ('approved','returned')) AS overdue
        FROM submissions s WHERE {where}
    """, param)

    # Avg response time (hours) for non-pending submissions
    avg_hours = await db.fetchval(f"""
        SELECT ROUND(EXTRACT(EPOCH FROM AVG(s.updated_at - s.submitted_at)) / 3600, 1)
        FROM submissions s
        WHERE {where} AND s.status != 'pending'
    """, param)

    # Recent 5 submissions
    recent = await db.fetch(f"""
        SELECT s.id, s.company_name, s.status, s.submitted_at,
               array_length(s.document_ids, 1) AS doc_count, s.deadline
        FROM submissions s WHERE {where}
        ORDER BY s.submitted_at DESC LIMIT 5
    """, param)

    return {
        "pending": counts["pending"],
        "reviewing": counts["reviewing"],
        "approved": counts["approved"],
        "returned": counts["returned"],
        "total": counts["total"],
        "overdue": counts["overdue"],
        "avg_response_hours": float(avg_hours) if avg_hours else None,
        "recent": [
            {
                "id": str(r["id"]),
                "company_name": r["company_name"],
                "status": r["status"],
                "doc_count": r["doc_count"] or 0,
                "submitted_at": r["submitted_at"].isoformat(),
                "deadline": r["deadline"].isoformat() if r["deadline"] else None,
            }
            for r in recent
        ],
    }


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

    # Notify provider owner
    await notify(db, req.provider_id, "new_submission",
                 f"Hồ sơ mới từ {company_name}",
                 f"{len(doc_uuids)} tài liệu cần đánh giá",
                 "/submissions")

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
                  s.deadline,
                  array_length(s.document_ids, 1) AS doc_count,
                  p.company_name AS provider_name, p.email AS provider_email,
                  a.company_name AS auditor_name
           FROM submissions s
           JOIN users p ON p.id = s.provider_id
           LEFT JOIN users a ON a.id = s.auditor_id
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
            "auditor_name": r["auditor_name"],
            "submitted_at": r["submitted_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
            "deadline": r["deadline"].isoformat() if r.get("deadline") else None,
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

    where, param = _provider_filter(user)
    rows = await db.fetch(
        f"""SELECT s.id, s.business_tenant, s.status, s.notes, s.auditor_notes,
                  s.submitted_at, s.updated_at, s.company_name,
                  s.auditor_id, s.document_ids, s.deadline,
                  array_length(s.document_ids, 1) AS doc_count
           FROM submissions s
           WHERE {where}
           ORDER BY s.submitted_at DESC""",
        param,
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
            "deadline": r["deadline"].isoformat() if r.get("deadline") else None,
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
    if user["role"] == "business":
        sub = await db.fetchrow(
            "SELECT document_ids FROM submissions WHERE id=$1 AND business_tenant=$2",
            submission_id, user.get("tenant_id"))
    elif user["role"] == "provider":
        where, param = _provider_filter(user, alias="")
        sub = await db.fetchrow(
            f"SELECT document_ids FROM submissions WHERE id = $1 AND {where.replace('$1', '$2')}",
            submission_id, param)
    else:
        raise HTTPException(403)
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

    # Get auditor evaluation for this submission
    eval_row = await db.fetchrow(
        "SELECT score, notes, checklist FROM submission_evaluations WHERE submission_id=$1 ORDER BY updated_at DESC LIMIT 1",
        submission_id)
    auditor_score = eval_row["score"] if eval_row else None
    auditor_notes = eval_row["notes"] if eval_row else None

    docs = []
    for r in rows:
        er = r["evaluation_result"]
        if isinstance(er, str):
            try: er = _json.loads(er)
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

    return {"documents": docs, "auditor_score": auditor_score, "auditor_notes": auditor_notes}


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

    if req.status not in ("assigned", "reviewing", "returned", "approved"):
        raise HTTPException(400, "Status không hợp lệ")

    where, param = _provider_filter(user, alias="")
    result = await db.execute(
        f"UPDATE submissions SET status = $1, auditor_notes = $2, updated_at = NOW() WHERE id = $3 AND {where.replace('$1', '$4')}",
        req.status, req.auditor_notes, submission_id, param,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Không tìm thấy hồ sơ")

    log.info(f"[submission] {submission_id} → {req.status}")

    # Notify business owner about status change
    sub_info = await db.fetchrow("SELECT business_tenant FROM submissions WHERE id=$1", submission_id)
    if sub_info:
        status_labels = {"reviewing": "đang được đánh giá", "returned": "đã bị trả lại", "approved": "đã được duyệt"}
        biz_owner = await db.fetchrow(
            "SELECT id FROM users WHERE id=$1 OR (tenant_id=$1 AND is_owner=true) LIMIT 1", sub_info["business_tenant"])
        if biz_owner:
            await notify(db, str(biz_owner["id"]), "status_change",
                         f"Hồ sơ {status_labels.get(req.status, req.status)}",
                         req.auditor_notes or "", "/documents")

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
        "UPDATE submissions SET auditor_id = $1, status = 'assigned', updated_at = NOW() WHERE id = $2 AND provider_id = $3",
        req.auditor_id, submission_id, user["sub"],
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Không tìm thấy hồ sơ")

    # Get names for notifications
    auditor_info = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", req.auditor_id)
    auditor_name = auditor_info["company_name"] if auditor_info else "Auditor"
    sub_info = await db.fetchrow("SELECT company_name, business_tenant FROM submissions WHERE id=$1", submission_id)

    # Notify auditor
    await notify(db, req.auditor_id, "new_submission",
                 f"Bạn được gán đánh giá hồ sơ từ {sub_info['company_name'] if sub_info else 'N/A'}",
                 "Vui lòng xem và đánh giá hồ sơ", "/submissions")

    # Notify business
    if sub_info:
        biz_owner = await db.fetchrow(
            "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", sub_info["business_tenant"])
        if biz_owner:
            await notify(db, str(biz_owner["id"]), "status_change",
                         f"Hồ sơ đã được gán cho auditor {auditor_name}",
                         "Hồ sơ của bạn đang được xử lý", "/documents")

    log.info(f"[submission] {submission_id} assigned to auditor {req.auditor_id}")
    return {"message": f"Đã gán cho {auditor_name}"}


# ── Comments ─────────────────────────────────────────────────────────────────

class CommentRequest(BaseModel):
    message: str


async def _check_submission_access(submission_id: str, user: dict, db):
    """Verify user can access this submission (business owner, provider owner, or assigned auditor)."""
    _validate_uuid(submission_id)
    if user["role"] == "business":
        row = await db.fetchrow(
            "SELECT id FROM submissions WHERE id=$1 AND business_tenant=$2", submission_id, user.get("tenant_id"))
    elif user["role"] == "provider":
        if user.get("is_owner"):
            row = await db.fetchrow(
                "SELECT id FROM submissions WHERE id=$1 AND provider_id=$2", submission_id, user["sub"])
        else:
            row = await db.fetchrow(
                "SELECT id FROM submissions WHERE id=$1 AND auditor_id=$2", submission_id, user["sub"])
    else:
        row = None
    if not row:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    return row


@router.get("/received/{submission_id}/comments")
async def list_comments(
    submission_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    await _check_submission_access(submission_id, user, db)
    rows = await db.fetch(
        "SELECT id, author_id, author_role, author_name, message, created_at FROM submission_comments WHERE submission_id=$1 ORDER BY created_at ASC",
        submission_id,
    )
    return {"comments": [
        {
            "id": str(r["id"]),
            "author_id": str(r["author_id"]),
            "author_role": r["author_role"],
            "author_name": r["author_name"],
            "message": r["message"],
            "created_at": r["created_at"].isoformat(),
        } for r in rows
    ]}


@router.post("/received/{submission_id}/comments")
async def add_comment(
    submission_id: str,
    req: CommentRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    await _check_submission_access(submission_id, user, db)
    if not req.message.strip():
        raise HTTPException(400, "Tin nhắn không được trống")

    # Get author display name
    author = await db.fetchrow("SELECT company_name, email FROM users WHERE id=$1", user["sub"])
    author_name = author["company_name"] or author["email"] if author else user.get("email", "")

    row = await db.fetchrow(
        """INSERT INTO submission_comments (submission_id, author_id, author_role, author_name, message)
           VALUES ($1, $2, $3, $4, $5) RETURNING id, created_at""",
        submission_id, user["sub"], user["role"], author_name, req.message.strip(),
    )

    log.info(f"[comment] {user['role']} commented on {submission_id}")

    # Notify the other parties
    sub_info = await db.fetchrow("SELECT provider_id, business_tenant, auditor_id FROM submissions WHERE id=$1", submission_id)
    if sub_info:
        msg_preview = req.message.strip()[:100]
        if user["role"] == "business":
            # Notify provider owner
            await notify(db, str(sub_info["provider_id"]), "comment",
                         f"Phản hồi mới từ {author_name}", msg_preview, "/submissions")
            # Notify assigned auditor (if different from provider owner)
            if sub_info["auditor_id"] and str(sub_info["auditor_id"]) != str(sub_info["provider_id"]):
                await notify(db, str(sub_info["auditor_id"]), "comment",
                             f"Phản hồi mới từ {author_name}", msg_preview, "/submissions")
        else:
            # Provider/auditor commenting → notify business owner
            biz_owner = await db.fetchrow(
                "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", sub_info["business_tenant"])
            if biz_owner:
                await notify(db, str(biz_owner["id"]), "comment",
                             f"Phản hồi mới từ {author_name}", msg_preview, "/submissions")
            # If auditor comments, also notify provider owner (and vice versa)
            if user["sub"] != str(sub_info["provider_id"]):
                await notify(db, str(sub_info["provider_id"]), "comment",
                             f"Phản hồi mới từ {author_name}", msg_preview, "/submissions")
            if sub_info["auditor_id"] and user["sub"] != str(sub_info["auditor_id"]):
                await notify(db, str(sub_info["auditor_id"]), "comment",
                             f"Phản hồi mới từ {author_name}", msg_preview, "/submissions")

    return {
        "id": str(row["id"]),
        "author_role": user["role"],
        "author_name": author_name,
        "message": req.message.strip(),
        "created_at": row["created_at"].isoformat(),
    }


# ── Evaluation / Scoring ─────────────────────────────────────────────────────

class EvaluationRequest(BaseModel):
    checklist: list = []
    score: Optional[int] = None
    notes: str = ""


@router.get("/received/{submission_id}/evaluation")
async def get_evaluation(
    submission_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    await _check_submission_access(submission_id, user, db)
    row = await db.fetchrow(
        "SELECT * FROM submission_evaluations WHERE submission_id=$1 ORDER BY updated_at DESC LIMIT 1",
        submission_id,
    )
    if not row:
        return {"evaluation": None}
    return {"evaluation": {
        "id": str(row["id"]),
        "auditor_id": str(row["auditor_id"]),
        "checklist": row["checklist"] if isinstance(row["checklist"], list) else (_json.loads(row["checklist"]) if isinstance(row["checklist"], str) else []),
        "score": row["score"],
        "notes": row["notes"],
        "updated_at": row["updated_at"].isoformat(),
    }}


@router.post("/received/{submission_id}/evaluation")
async def save_evaluation(
    submission_id: str,
    req: EvaluationRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    if user["role"] != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")
    await _check_submission_access(submission_id, user, db)

    checklist_json = _json.dumps(req.checklist)

    await db.execute("""
        INSERT INTO submission_evaluations (submission_id, auditor_id, checklist, score, notes)
        VALUES ($1, $2, $3::jsonb, $4, $5)
        ON CONFLICT (submission_id, auditor_id)
        DO UPDATE SET checklist=$3::jsonb, score=$4, notes=$5, updated_at=NOW()
    """, submission_id, user["sub"], checklist_json, req.score, req.notes)

    # Update submission status based on score
    sub_info = await db.fetchrow(
        "SELECT provider_id, business_tenant, company_name, status FROM submissions WHERE id=$1", submission_id)
    if sub_info:
        # Auto-update status to 'reviewing' if still assigned
        if sub_info["status"] in ("assigned", "pending"):
            await db.execute("UPDATE submissions SET status='reviewing', updated_at=NOW() WHERE id=$1", submission_id)

        # Get evaluator name
        evaluator = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", user["sub"])
        eval_name = evaluator["company_name"] if evaluator else "Auditor"
        score_text = f"Điểm: {req.score}/100" if req.score is not None else ""

        # Notify provider owner
        if str(sub_info["provider_id"]) != user["sub"]:
            await notify(db, str(sub_info["provider_id"]), "status_change",
                         f"{eval_name} đã đánh giá hồ sơ từ {sub_info['company_name']}",
                         f"{score_text}. {req.notes[:80] if req.notes else ''}", "/submissions")

        # Notify business owner
        biz_owner = await db.fetchrow(
            "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", sub_info["business_tenant"])
        if biz_owner:
            await notify(db, str(biz_owner["id"]), "status_change",
                         f"Hồ sơ đã được đánh giá bởi {eval_name}",
                         f"{score_text}. {req.notes[:80] if req.notes else ''}", "/submissions")

    log.info(f"[eval] {user['sub']} scored submission {submission_id}: {req.score}")
    return {"message": "Đã lưu đánh giá", "score": req.score}


# ── Provider/Auditor: approve final — close the loop ─────────────────────────

@router.post("/received/{submission_id}/approve-final")
async def approve_final(
    submission_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Auditor/Provider approves submission → auto-finalize for business."""
    _validate_uuid(submission_id)
    if user["role"] != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")

    where, param = _provider_filter(user, alias="")
    sub = await db.fetchrow(
        f"SELECT * FROM submissions WHERE id=$1 AND {where.replace('$1', '$2')}",
        submission_id, param)
    if not sub:
        raise HTTPException(404)
    if sub["status"] == "approved":
        raise HTTPException(400, "Hồ sơ đã được phê duyệt trước đó")

    # Update status to approved
    await db.execute(
        "UPDATE submissions SET status='approved', updated_at=NOW() WHERE id=$1", submission_id)

    # Get auditor evaluation score
    eval_row = await db.fetchrow(
        "SELECT score, notes FROM submission_evaluations WHERE submission_id=$1 ORDER BY updated_at DESC LIMIT 1",
        submission_id)
    auditor_score = eval_row["score"] if eval_row else None
    auditor_notes = eval_row["notes"] if eval_row else ""

    # Promote all documents + mark as CB-approved
    doc_ids = sub["document_ids"] or []
    for doc_id in doc_ids:
        # Update evaluation_result to reflect CB approval + set score
        cb_result = _json.dumps({
            "overall_status": "cb_approved",
            "cb_approved_by": user.get("email", ""),
            "cb_score": auditor_score,
            "cb_notes": auditor_notes,
        })
        await db.execute("""
            UPDATE documents SET uploaded_at=NOW(), compliance_score=$1, evaluation_result=$2::jsonb
            WHERE id=$3 AND tenant_id=$4
        """, auditor_score, cb_result, str(doc_id), sub["business_tenant"])

    # Get names
    approver = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", user["sub"])
    approver_name = approver["company_name"] if approver else "Auditor"

    # Notify business owner with congratulations
    biz_owner = await db.fetchrow(
        "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", sub["business_tenant"])
    if biz_owner:
        await notify(db, str(biz_owner["id"]), "certificate",
                     f"Chúc mừng! Tài liệu đã được phê duyệt bởi {approver_name}",
                     "Tài liệu đã được cập nhật vào hệ thống của bạn. Hồ sơ đã hoàn tất.",
                     "/documents")

    # Also notify provider owner if auditor approved
    if not user.get("is_owner") and str(sub["provider_id"]) != user["sub"]:
        await notify(db, str(sub["provider_id"]), "status_change",
                     f"{approver_name} đã phê duyệt hồ sơ từ {sub['company_name']}",
                     "", "/submissions")

    log.info(f"[submission] {submission_id} approved by {user['sub']}")
    return {"message": f"Đã phê duyệt hồ sơ từ {sub['company_name']}. Doanh nghiệp sẽ hoàn tất hồ sơ."}


# ── Business: reupload document in submission ─────────────────────────────────

@router.put("/received/{submission_id}/replace-document")
async def replace_submission_document(
    submission_id: str,
    request: dict,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Business replaces an old document in a submission with a new revision."""
    _validate_uuid(submission_id)
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho doanh nghiệp")

    old_doc_id = request.get("old_doc_id")
    new_doc_id = request.get("new_doc_id")
    if not old_doc_id or not new_doc_id:
        raise HTTPException(400, "Thiếu old_doc_id hoặc new_doc_id")
    _validate_uuid(old_doc_id)
    _validate_uuid(new_doc_id)

    sub = await db.fetchrow(
        "SELECT id, document_ids FROM submissions WHERE id=$1 AND business_tenant=$2",
        submission_id, user.get("tenant_id"))
    if not sub:
        raise HTTPException(404)

    # Verify new doc belongs to tenant
    new_doc = await db.fetchrow(
        "SELECT id FROM documents WHERE id=$1 AND tenant_id=$2", new_doc_id, user.get("tenant_id"))
    if not new_doc:
        raise HTTPException(400, "Tài liệu mới không hợp lệ")

    # Replace old_doc_id with new_doc_id in the array
    doc_ids = [str(d) for d in (sub["document_ids"] or [])]
    if old_doc_id in doc_ids:
        doc_ids[doc_ids.index(old_doc_id)] = new_doc_id
    else:
        doc_ids.append(new_doc_id)

    await db.execute(
        "UPDATE submissions SET document_ids = $1::uuid[], updated_at = NOW() WHERE id = $2",
        doc_ids, submission_id)

    # Notify provider + auditor
    sub_info = await db.fetchrow("SELECT provider_id, auditor_id, company_name FROM submissions WHERE id=$1", submission_id)
    if sub_info:
        await notify(db, str(sub_info["provider_id"]), "status_change",
                     f"{sub_info['company_name']} đã cập nhật tài liệu",
                     "Phiên bản mới đã được upload", "/submissions")
        if sub_info["auditor_id"]:
            await notify(db, str(sub_info["auditor_id"]), "status_change",
                         f"{sub_info['company_name']} đã cập nhật tài liệu",
                         "Phiên bản mới đã được upload", "/submissions")

    log.info(f"[submission] {submission_id} doc replaced: {old_doc_id} → {new_doc_id}")
    return {"message": "Đã cập nhật tài liệu trong hồ sơ"}


# ── Business: get revision history for a doc in submission ────────────────────

@router.get("/received/{submission_id}/doc-revisions/{doc_type_id}")
async def submission_doc_revisions(
    submission_id: str,
    doc_type_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Get all revisions of a doc_type within a submission's business tenant."""
    _validate_uuid(submission_id)
    await _check_submission_access(submission_id, user, db)

    # Always use the business tenant from the submission, not the current user's tenant
    sub = await db.fetchrow("SELECT business_tenant FROM submissions WHERE id=$1", submission_id)
    if not sub:
        raise HTTPException(404)
    biz_tenant = sub["business_tenant"]

    rows = await db.fetch(
        """SELECT id, original_filename, compliance_score, file_size, uploaded_at,
                  doc_type, evaluation_result
           FROM documents WHERE tenant_id=$1 AND doc_type=$2
           ORDER BY uploaded_at DESC""",
        biz_tenant, doc_type_id)

    revisions = []
    for r in rows:
        er = r["evaluation_result"]
        if isinstance(er, str):
            import json; er = json.loads(er) if er else {}
        elif er is None:
            er = {}
        revisions.append({
            "id": str(r["id"]),
            "original_filename": r["original_filename"],
            "compliance_score": r["compliance_score"],
            "overall_status": er.get("overall_status"),
            "file_size": r["file_size"],
            "uploaded_at": r["uploaded_at"].isoformat(),
        })

    return {"doc_type": doc_type_id, "revisions": revisions, "total": len(revisions)}


# ── Business: finalize approved submission ────────────────────────────────────

@router.post("/received/{submission_id}/finalize")
async def finalize_submission(
    submission_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Business saves approved submission: promote latest revision, mark as CB-approved, archive submission."""
    _validate_uuid(submission_id)
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho doanh nghiệp")

    sub = await db.fetchrow(
        "SELECT * FROM submissions WHERE id=$1 AND business_tenant=$2",
        submission_id, user.get("tenant_id"))
    if not sub:
        raise HTTPException(404)
    if sub["status"] != "approved":
        raise HTTPException(400, "Hồ sơ chưa được duyệt")

    # For each document in submission, promote it (set uploaded_at = NOW to make it current)
    doc_ids = sub["document_ids"] or []
    for doc_id in doc_ids:
        # Mark as CB-approved by updating evaluation_result
        await db.execute("""
            UPDATE documents SET uploaded_at = NOW()
            WHERE id = $1 AND tenant_id = $2
        """, str(doc_id), user.get("tenant_id"))

    # Delete the submission (archive)
    await db.execute("DELETE FROM submissions WHERE id = $1", submission_id)

    log.info(f"[submission] {submission_id} finalized by business {user['sub']}")
    return {"message": "Đã lưu và hoàn tất hồ sơ"}


# ── Deadline ─────────────────────────────────────────────────────────────────

class DeadlineRequest(BaseModel):
    deadline: Optional[str] = None


@router.put("/received/{submission_id}/deadline")
async def set_deadline(
    submission_id: str,
    req: DeadlineRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    _validate_uuid(submission_id)
    if user["role"] != "provider" or not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức mới được đặt deadline")

    deadline_val = None
    if req.deadline:
        try:
            deadline_val = datetime.fromisoformat(req.deadline.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Định dạng deadline không hợp lệ")

    result = await db.execute(
        "UPDATE submissions SET deadline=$1, updated_at=NOW() WHERE id=$2 AND provider_id=$3",
        deadline_val, submission_id, user["sub"],
    )
    if result == "UPDATE 0":
        raise HTTPException(404)
    return {"message": "Đã cập nhật deadline"}
