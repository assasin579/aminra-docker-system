"""Onsite Audit Module — visits, checklist, NCR, reports, templates."""

import logging
import io
import json as _json
from uuid import UUID as _UUID, uuid4
from pathlib import Path
from typing import Optional
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Request
from fastapi.responses import Response
from pydantic import BaseModel

from auth.db import get_db
from auth.identity import resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from auth.notification_router import notify

log = logging.getLogger("aminra.audits")
router = APIRouter()


def _validate_uuid(v: str) -> str:
    try:
        _UUID(v)
    except ValueError:
        raise HTTPException(400, "Invalid ID")
    return v


def _audit_filter(user: dict):
    """Owner sees all visits for their provider, auditor sees only assigned."""
    if user.get("is_owner"):
        return "provider_id = $1", user["sub"]
    else:
        return "auditor_id = $1", user["sub"]


def _require_provider(user: dict):
    if user.get("role") != "provider":
        raise HTTPException(403, "Chỉ dành cho tổ chức")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE A: Visit CRUD + Assign + Status + Populate Checklist
# ═══════════════════════════════════════════════════════════════════════════════


class VisitCreate(BaseModel):
    business_tenant: str
    visit_type: str  # initial, renewal, surprise
    scheduled_date: str
    location: str = ""
    notes: str = ""
    template_id: Optional[str] = None


class VisitUpdate(BaseModel):
    visit_type: Optional[str] = None
    scheduled_date: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


# ── Business Portfolio ──
@router.get("/businesses")
async def list_businesses(user=Depends(get_current_user), db=Depends(get_db)):
    """List all businesses this CB serves, with aggregated stats."""
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    provider_id = user.get("tenant_id") or user["sub"]

    rows = await db.fetch(
        """
        WITH biz AS (
            SELECT DISTINCT business_tenant FROM submissions WHERE provider_id=$1
            UNION
            SELECT DISTINCT business_tenant FROM audit_visits WHERE provider_id=$1
        )
        SELECT b.business_tenant,
            u.company_name, u.email, u.phone, u.address,
            (SELECT COUNT(*) FROM submissions WHERE business_tenant=b.business_tenant AND provider_id=$1) AS submission_count,
            (SELECT COUNT(*) FROM submissions WHERE business_tenant=b.business_tenant AND provider_id=$1 AND status='approved') AS approved_count,
            (SELECT COUNT(*) FROM halal_certificates WHERE business_tenant=b.business_tenant AND issued_by=$1 AND status='active') AS active_certs,
            (SELECT COUNT(*) FROM halal_certificates WHERE business_tenant=b.business_tenant AND issued_by=$1 AND status='active' AND expiry_date < NOW() + INTERVAL '90 days') AS expiring_soon,
            (SELECT MIN(expiry_date) FROM halal_certificates WHERE business_tenant=b.business_tenant AND issued_by=$1 AND status='active') AS nearest_expiry,
            (SELECT COUNT(*) FROM audit_visits WHERE business_tenant=b.business_tenant AND provider_id=$1) AS audit_count,
            (SELECT MAX(scheduled_date) FROM audit_visits WHERE business_tenant=b.business_tenant AND provider_id=$1) AS last_audit,
            (SELECT compliance_score FROM audit_visits WHERE business_tenant=b.business_tenant AND provider_id=$1 AND compliance_score IS NOT NULL ORDER BY scheduled_date DESC LIMIT 1) AS latest_score,
            (SELECT COUNT(*) FROM audit_ncr n JOIN audit_visits v ON v.id=n.visit_id WHERE v.business_tenant=b.business_tenant AND v.provider_id=$1 AND n.status='open') AS open_ncr
        FROM biz b
        LEFT JOIN users u ON (u.id=b.business_tenant OR (u.tenant_id=b.business_tenant AND u.is_owner=true))
        WHERE u.company_name IS NOT NULL
        ORDER BY u.company_name
    """,
        provider_id,
    )

    return {
        "businesses": [
            {
                "id": str(r["business_tenant"]),
                "company_name": r["company_name"] or "N/A",
                "email": r["email"] or "",
                "phone": r.get("phone") or "",
                "address": r.get("address") or "",
                "submission_count": r["submission_count"],
                "approved_count": r["approved_count"],
                "active_certs": r["active_certs"],
                "expiring_soon": r["expiring_soon"],
                "nearest_expiry": r["nearest_expiry"].isoformat() if r["nearest_expiry"] else None,
                "audit_count": r["audit_count"],
                "last_audit": r["last_audit"].isoformat() if r["last_audit"] else None,
                "latest_score": r["latest_score"],
                "open_ncr": r["open_ncr"],
            }
            for r in rows
        ]
    }


# ── Business dossier (consolidated docs + revisions) ──
@router.get("/businesses/{business_id}/dossier")
async def business_dossier(business_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """All submissions + all documents (grouped by doc_type with revision history) +
    audit visits for one business. Provider-only — `business_id` is the business tenant id.

    Doc revisions are pulled from `documents` table for the business tenant. Each doc_type
    bucket is sorted newest-first so the head is the current revision.
    """
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    provider_id = user.get("tenant_id") or user["sub"]

    biz = await db.fetchrow(
        "SELECT id, company_name, email, phone, address FROM users "
        "WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1",
        business_id,
    )
    if not biz:
        raise HTTPException(404, "Doanh nghiệp không tồn tại")

    submissions = await db.fetch(
        """
        SELECT id, status, document_ids, deadline, auditor_id, auditor_notes,
               submitted_at, updated_at
        FROM submissions
        WHERE business_tenant=$1 AND provider_id=$2
        ORDER BY submitted_at DESC NULLS LAST, updated_at DESC
    """,
        business_id,
        provider_id,
    )

    docs = await db.fetch(
        """
        SELECT id, original_filename, doc_type, compliance_score, file_size,
               uploaded_at, evaluation_result, status
        FROM documents
        WHERE tenant_id=$1
        ORDER BY doc_type, uploaded_at DESC
    """,
        business_id,
    )

    by_doc_type: dict[str, list] = {}
    for d in docs:
        er = d["evaluation_result"]
        if isinstance(er, str):
            try:
                er = _json.loads(er) if er else {}
            except Exception:
                er = {}
        elif er is None:
            er = {}
        by_doc_type.setdefault(d["doc_type"] or "_unsorted", []).append(
            {
                "id": str(d["id"]),
                "original_filename": d["original_filename"],
                "compliance_score": d["compliance_score"],
                "file_size": d["file_size"],
                "uploaded_at": d["uploaded_at"].isoformat(),
                "overall_status": er.get("overall_status"),
                "cb_approved_by": er.get("cb_approved_by"),
                "status": d["status"],
            }
        )

    visits = await db.fetch(
        """
        SELECT id, status, visit_type, scheduled_date, compliance_score, auditor_id
        FROM audit_visits
        WHERE business_tenant=$1 AND provider_id=$2
        ORDER BY scheduled_date DESC
    """,
        business_id,
        provider_id,
    )

    return {
        "business": {
            "id": str(biz["id"]),
            "company_name": biz["company_name"] or "N/A",
            "email": biz["email"] or "",
            "phone": biz["phone"] or "",
            "address": biz["address"] or "",
        },
        "submissions": [
            {
                "id": str(s["id"]),
                "status": s["status"],
                "document_ids": [str(x) for x in (s["document_ids"] or [])],
                "deadline": s["deadline"].isoformat() if s["deadline"] else None,
                "auditor_id": str(s["auditor_id"]) if s["auditor_id"] else None,
                "auditor_notes": s["auditor_notes"] or "",
                "submitted_at": s["submitted_at"].isoformat() if s["submitted_at"] else None,
                "updated_at": s["updated_at"].isoformat(),
            }
            for s in submissions
        ],
        "documents_by_type": [
            {
                "doc_type": dt,
                "revisions": revs,
                "current": revs[0] if revs else None,
                "revision_count": len(revs),
            }
            for dt, revs in by_doc_type.items()
        ],
        "audit_visits": [
            {
                "id": str(v["id"]),
                "status": v["status"],
                "visit_type": v["visit_type"],
                "scheduled_date": v["scheduled_date"].isoformat(),
                "compliance_score": v["compliance_score"],
                "auditor_id": str(v["auditor_id"]) if v["auditor_id"] else None,
            }
            for v in visits
        ],
    }


# ── Business composite score ──
@router.get("/businesses/{business_id}/score")
async def business_score(business_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Composite score for a business under this provider's relationship.

    Components:
    - doc_score: avg compliance_score across the LATEST revision of each doc_type
                 belonging to this business (limited to docs within approved submissions
                 of this provider). Documents are the foundation — they prove the dossier
                 was acceptable on paper.
    - audit_score: avg compliance_score across COMPLETED on-site visits by this provider.
                   Audits weigh more because they're field-verified, not paper.
    - composite: 40% doc + 60% audit when both exist; otherwise whichever is available.

    Why this weighting: documents are necessary but auditable in the office; audit visits
    are the ground truth. A business with great docs but failing audits should not score
    high. A business with no audit yet shows doc-only score so providers see early signal.
    """
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    provider_id = user.get("tenant_id") or user["sub"]

    biz_exists = await db.fetchval(
        "SELECT 1 FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", business_id
    )
    if not biz_exists:
        raise HTTPException(404, "Doanh nghiệp không tồn tại")

    # W3-M11 — Restrict doc_score to docs that appear in submissions assigned to
    # THIS provider. Otherwise a doc evaluated by another CB (or never submitted
    # at all) would inflate this provider's view of the business.
    doc_row = await db.fetchrow(
        """
        WITH provider_doc_ids AS (
          SELECT DISTINCT unnest(document_ids)::uuid AS doc_id
          FROM submissions
          WHERE business_tenant=$1 AND provider_id=$2
        ),
        latest AS (
          SELECT DISTINCT ON (d.doc_type) d.doc_type, d.compliance_score
          FROM documents d
          JOIN provider_doc_ids pd ON pd.doc_id = d.id
          WHERE d.tenant_id=$1
            AND d.doc_type IS NOT NULL
            AND d.compliance_score IS NOT NULL
          ORDER BY d.doc_type, d.uploaded_at DESC
        )
        SELECT
          COUNT(*)                              AS doc_types,
          ROUND(AVG(compliance_score)::numeric) AS doc_score,
          MIN(compliance_score)                 AS doc_min,
          MAX(compliance_score)                 AS doc_max
        FROM latest
    """,
        business_id,
        provider_id,
    )

    # W3-M12 — Average only over COMPLETED audit visits. Including in-progress
    # visits with placeholder scores skewed the composite.
    audit_row = await db.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE compliance_score IS NOT NULL
                            AND status IN ('completed', 'report_submitted')) AS scored_visits,
          COUNT(*) FILTER (WHERE status IN ('completed', 'report_submitted')) AS completed_visits,
          ROUND(AVG(compliance_score) FILTER (
                  WHERE status IN ('completed', 'report_submitted')
                )::numeric)                                                    AS audit_score,
          MIN(compliance_score) FILTER (WHERE status IN ('completed', 'report_submitted')) AS audit_min,
          MAX(compliance_score) FILTER (WHERE status IN ('completed', 'report_submitted')) AS audit_max
        FROM audit_visits
        WHERE business_tenant=$1 AND provider_id=$2
    """,
        business_id,
        provider_id,
    )

    doc_score = int(doc_row["doc_score"]) if doc_row["doc_score"] is not None else None
    audit_score = int(audit_row["audit_score"]) if audit_row["audit_score"] is not None else None

    if doc_score is not None and audit_score is not None:
        composite = round(doc_score * 0.4 + audit_score * 0.6)
    elif doc_score is not None:
        composite = doc_score
    elif audit_score is not None:
        composite = audit_score
    else:
        composite = None

    if composite is None:
        rating = "unrated"
    elif composite >= 90:
        rating = "excellent"
    elif composite >= 75:
        rating = "good"
    elif composite >= 60:
        rating = "fair"
    else:
        rating = "needs_improvement"

    return {
        "business_id": business_id,
        "composite_score": composite,
        "rating": rating,
        "doc_component": {
            "score": doc_score,
            "doc_types_evaluated": doc_row["doc_types"] or 0,
            "min": doc_row["doc_min"],
            "max": doc_row["doc_max"],
            "weight": 0.4
            if doc_score is not None and audit_score is not None
            else (1.0 if doc_score is not None else 0),
        },
        "audit_component": {
            "score": audit_score,
            "completed_visits": audit_row["completed_visits"] or 0,
            "scored_visits": audit_row["scored_visits"] or 0,
            "min": audit_row["audit_min"],
            "max": audit_row["audit_max"],
            "weight": 0.6
            if doc_score is not None and audit_score is not None
            else (1.0 if audit_score is not None else 0),
        },
    }


# ── Stats ──
@router.get("/stats")
async def audit_stats(user=Depends(get_current_user), db=Depends(get_db)):
    _require_provider(user)
    where, param = _audit_filter(user)
    counts = await db.fetchrow(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE status = 'scheduled')        AS scheduled,
            COUNT(*) FILTER (WHERE status = 'in_progress')      AS in_progress,
            COUNT(*) FILTER (WHERE status = 'completed')        AS completed,
            COUNT(*) FILTER (WHERE status = 'report_submitted') AS report_submitted,
            COUNT(*)                                             AS total
        FROM audit_visits WHERE {where}
    """,
        param,
    )
    recent = await db.fetch(
        f"""
        SELECT v.id, v.business_tenant, v.status, v.scheduled_date, v.visit_type,
               u.company_name AS business_name
        FROM audit_visits v
        LEFT JOIN users u ON u.id = v.business_tenant OR u.tenant_id = v.business_tenant AND u.is_owner = true
        WHERE {where.replace("provider_id", "v.provider_id").replace("auditor_id", "v.auditor_id")}
        ORDER BY v.scheduled_date DESC LIMIT 5
    """,
        param,
    )
    return {
        **{k: counts[k] for k in ["scheduled", "in_progress", "completed", "report_submitted", "total"]},
        "recent": [
            {
                "id": str(r["id"]),
                "business_name": r["business_name"] or "N/A",
                "status": r["status"],
                "visit_type": r["visit_type"],
                "scheduled_date": r["scheduled_date"].isoformat(),
            }
            for r in recent
        ],
    }


# ── Templates (Phase E — placed before /{id} routes) ──
@router.get("/templates")
async def list_templates(user=Depends(get_current_user), db=Depends(get_db)):
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    tid = user.get("tenant_id") or user["sub"]
    rows = await db.fetch("SELECT * FROM audit_checklist_templates WHERE provider_id=$1 ORDER BY created_at DESC", tid)
    return {
        "templates": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "standard": r["standard"],
                "items": r["items"]
                if isinstance(r["items"], list)
                else _json.loads(r["items"])
                if isinstance(r["items"], str)
                else [],
                "item_count": len(r["items"]) if isinstance(r["items"], list) else 0,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/templates")
async def create_template(req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    tid = user.get("tenant_id") or user["sub"]
    row = await db.fetchrow(
        "INSERT INTO audit_checklist_templates (provider_id, name, standard, items) VALUES ($1,$2,$3,$4::jsonb) RETURNING id",
        tid,
        req.get("name", ""),
        req.get("standard", ""),
        _json.dumps(req.get("items", [])),
    )
    return {"id": str(row["id"]), "message": "Đã tạo template"}


@router.put("/templates/{tid}")
async def update_template(tid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(tid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403)
    provider = user.get("tenant_id") or user["sub"]
    updates, params, idx = [], [], 1
    if "name" in req:
        updates.append(f"name=${idx}")
        params.append(req["name"])
        idx += 1
    if "standard" in req:
        updates.append(f"standard=${idx}")
        params.append(req["standard"])
        idx += 1
    if "items" in req:
        updates.append(f"items=${idx}::jsonb")
        params.append(_json.dumps(req["items"]))
        idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    params.extend([tid, provider])
    await db.execute(
        f"UPDATE audit_checklist_templates SET {', '.join(updates)} WHERE id=${idx} AND provider_id=${idx + 1}", *params
    )
    return {"message": "Đã cập nhật template"}


@router.delete("/templates/{tid}")
async def delete_template(tid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(tid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403)
    provider = user.get("tenant_id") or user["sub"]
    await db.execute("DELETE FROM audit_checklist_templates WHERE id=$1 AND provider_id=$2", tid, provider)
    return {"message": "Đã xóa"}


# ── List visits ──
@router.get("/")
async def list_visits(user=Depends(get_current_user), db=Depends(get_db)):
    _require_provider(user)
    where, param = _audit_filter(user)
    rows = await db.fetch(
        f"""
        SELECT v.*, u.company_name AS business_name, a.company_name AS auditor_name
        FROM audit_visits v
        LEFT JOIN users u ON (u.id = v.business_tenant OR (u.tenant_id = v.business_tenant AND u.is_owner = true))
        LEFT JOIN users a ON a.id = v.auditor_id
        WHERE v.{where}
        ORDER BY v.scheduled_date DESC
    """,
        param,
    )
    return {
        "visits": [
            {
                "id": str(r["id"]),
                "business_tenant": str(r["business_tenant"]),
                "business_name": r["business_name"] or "N/A",
                "auditor_name": r["auditor_name"],
                "visit_type": r["visit_type"],
                "status": r["status"],
                "scheduled_date": r["scheduled_date"].isoformat(),
                "location": r["location"],
                "compliance_score": r["compliance_score"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


# ── Create visit ──
@router.post("/")
async def create_visit(req: VisitCreate, user=Depends(get_current_user), db=Depends(get_db)):
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    _validate_uuid(req.business_tenant)
    if req.visit_type not in ("initial", "renewal", "surprise"):
        raise HTTPException(400, "visit_type không hợp lệ")

    provider = user.get("tenant_id") or user["sub"]
    template_id = req.template_id
    if template_id:
        _validate_uuid(template_id)

    row = await db.fetchrow(
        """
        INSERT INTO audit_visits (business_tenant, provider_id, template_id, visit_type, scheduled_date, location, notes)
        VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
    """,
        req.business_tenant,
        provider,
        template_id,
        req.visit_type,
        date.fromisoformat(req.scheduled_date),
        req.location,
        req.notes,
    )

    log.info(f"[audit] Created visit {row['id']} for {req.business_tenant}")
    return {"id": str(row["id"]), "message": "Đã tạo chuyến kiểm định"}


# ── Get visit detail ──
@router.get("/{vid}")
async def get_visit(vid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    where, param = _audit_filter(user)
    row = await db.fetchrow(
        f"""
        SELECT v.*, u.company_name AS business_name, a.company_name AS auditor_name
        FROM audit_visits v
        LEFT JOIN users u ON (u.id = v.business_tenant OR (u.tenant_id = v.business_tenant AND u.is_owner = true))
        LEFT JOIN users a ON a.id = v.auditor_id
        WHERE v.id = $1 AND v.{where.replace("$1", "$2")}
    """,
        vid,
        param,
    )
    if not row:
        raise HTTPException(404)

    items = await db.fetch("SELECT * FROM audit_visit_items WHERE visit_id=$1 ORDER BY category, created_at", vid)
    ncrs = await db.fetch("SELECT * FROM audit_ncr WHERE visit_id=$1 ORDER BY created_at", vid)

    return {
        "visit": {
            "id": str(row["id"]),
            "business_tenant": str(row["business_tenant"]),
            "business_name": row["business_name"] or "N/A",
            "auditor_name": row["auditor_name"],
            "visit_type": row["visit_type"],
            "status": row["status"],
            "scheduled_date": row["scheduled_date"].isoformat(),
            "location": row["location"],
            "notes": row["notes"],
            "compliance_score": row["compliance_score"],
            "report_pdf_path": bool(row["report_pdf_path"]),
            "start_gps": row["start_gps"],
            "end_gps": row["end_gps"],
            "has_auditor_sig": bool(row["auditor_signature_path"]),
            "has_business_sig": bool(row["business_signature_path"]),
            "created_at": row["created_at"].isoformat(),
        },
        "items": [
            {
                "id": str(i["id"]),
                "code": i.get("code") or "",
                "category": i["category"],
                "criteria": i["criteria"],
                "severity": i["severity"],
                "result": i["result"],
                "note": i["note"],
                "clause": i.get("clause") or "",
                "audit_method": i.get("audit_method") or "",
                "documents": i.get("documents") or "",
                "evidence": i.get("evidence") or "",
                "corrective_action": i.get("corrective_action") or "",
                "corrective_status": i.get("corrective_status"),
                "photo_paths": i["photo_paths"]
                if isinstance(i["photo_paths"], list)
                else (_json.loads(i["photo_paths"]) if isinstance(i["photo_paths"], str) else []),
            }
            for i in items
        ],
        "ncrs": [
            {
                "id": str(n["id"]),
                "description": n["description"],
                "severity": n["severity"],
                "status": n["status"],
                "corrective_action": n["corrective_action"],
                "deadline": n["deadline"].isoformat() if n["deadline"] else None,
                "photo_paths": n["photo_paths"]
                if isinstance(n["photo_paths"], list)
                else (_json.loads(n["photo_paths"]) if isinstance(n["photo_paths"], str) else []),
                "evidence_paths": n["evidence_paths"]
                if isinstance(n["evidence_paths"], list)
                else (_json.loads(n["evidence_paths"]) if isinstance(n["evidence_paths"], str) else []),
                "created_at": n["created_at"].isoformat(),
            }
            for n in ncrs
        ],
    }


# ── Update visit ──
@router.put("/{vid}")
async def update_visit(vid: str, req: VisitUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403)
    provider = user.get("tenant_id") or user["sub"]
    updates, params, idx = [], [], 1
    if req.visit_type:
        updates.append(f"visit_type=${idx}")
        params.append(req.visit_type)
        idx += 1
    if req.scheduled_date:
        updates.append(f"scheduled_date=${idx}")
        params.append(date.fromisoformat(req.scheduled_date))
        idx += 1
    if req.location is not None:
        updates.append(f"location=${idx}")
        params.append(req.location)
        idx += 1
    if req.notes is not None:
        updates.append(f"notes=${idx}")
        params.append(req.notes)
        idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    params.extend([vid, provider])
    await db.execute(
        f"UPDATE audit_visits SET {', '.join(updates)} WHERE id=${idx} AND provider_id=${idx + 1}", *params
    )
    return {"message": "Đã cập nhật"}


# ── Delete visit ──
@router.delete("/{vid}")
async def delete_visit(vid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403)
    provider = user.get("tenant_id") or user["sub"]
    result = await db.execute(
        "DELETE FROM audit_visits WHERE id=$1 AND provider_id=$2 AND status='scheduled'", vid, provider
    )
    if result == "DELETE 0":
        raise HTTPException(400, "Chỉ xóa được chuyến ở trạng thái 'Đã lên lịch'")
    return {"message": "Đã xóa"}


# ── Assign auditor ──
@router.put("/{vid}/assign")
async def assign_visit_auditor(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    provider = user.get("tenant_id") or user["sub"]
    auditor_id = req.get("auditor_id")
    if not auditor_id:
        raise HTTPException(400, "Thiếu auditor_id")
    _validate_uuid(auditor_id)

    auditor = await db.fetchrow(
        "SELECT id, company_name FROM users WHERE id=$1 AND tenant_id=$2 AND is_owner=false AND role='provider'",
        auditor_id,
        provider,
    )
    if not auditor:
        raise HTTPException(404, "Auditor không tồn tại")

    await db.execute("UPDATE audit_visits SET auditor_id=$1 WHERE id=$2 AND provider_id=$3", auditor_id, vid, provider)

    # Notify auditor
    visit = await db.fetchrow("SELECT business_tenant, scheduled_date FROM audit_visits WHERE id=$1", vid)
    if visit:
        biz = await db.fetchrow(
            "SELECT company_name FROM users WHERE id=$1 OR (tenant_id=$1 AND is_owner=true) LIMIT 1",
            visit["business_tenant"],
        )
        biz_name = biz["company_name"] if biz else "N/A"
        await notify(
            db,
            auditor_id,
            "audit",
            f"Bạn được gán kiểm định tại {biz_name}",
            f"Ngày: {visit['scheduled_date']}",
            "/audits",
        )

    return {"message": f"Đã gán {auditor['company_name']}"}


# ── Update status ──
@router.put("/{vid}/status")
async def update_visit_status(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    new_status = req.get("status")
    if new_status not in ("scheduled", "in_progress", "completed", "report_submitted"):
        raise HTTPException(400, "Status không hợp lệ")

    where, param = _audit_filter(user)
    result = await db.execute(
        f"UPDATE audit_visits SET status=$1 WHERE id=$2 AND {where.replace('$1', '$3')}", new_status, vid, param
    )
    if result == "UPDATE 0":
        raise HTTPException(404)

    # Auto-calc compliance score when completing
    if new_status == "completed":
        items = await db.fetch("SELECT result FROM audit_visit_items WHERE visit_id=$1", vid)
        if items:
            answered = [i for i in items if i["result"] and i["result"] != "na"]
            passed = [i for i in answered if i["result"] == "conform"]
            score = round(len(passed) / len(answered) * 100) if answered else 0
            await db.execute("UPDATE audit_visits SET compliance_score=$1 WHERE id=$2", score, vid)

    return {"message": f"Đã cập nhật: {new_status}"}


# ── Populate checklist from template ──
@router.post("/{vid}/populate-checklist")
async def populate_checklist(vid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    visit = await db.fetchrow("SELECT template_id FROM audit_visits WHERE id=$1", vid)
    if not visit or not visit["template_id"]:
        raise HTTPException(400, "Chuyến chưa gắn template")

    template = await db.fetchrow("SELECT items FROM audit_checklist_templates WHERE id=$1", visit["template_id"])
    if not template:
        raise HTTPException(404, "Template không tồn tại")

    items = template["items"]
    if isinstance(items, str):
        items = _json.loads(items)

    # Clear existing items
    await db.execute("DELETE FROM audit_visit_items WHERE visit_id=$1", vid)

    # Insert from template
    for item in items:
        await db.execute(
            """
            INSERT INTO audit_visit_items (visit_id, code, category, criteria, severity, clause, audit_method, documents)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
            vid,
            item.get("code", ""),
            item.get("category", ""),
            item.get("criteria", ""),
            item.get("severity", "minor"),
            item.get("clause", ""),
            item.get("audit_method", ""),
            item.get("documents", ""),
        )

    return {"message": f"Đã tạo {len(items)} checklist items", "count": len(items)}


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE B: Field Recording — Items, Photos, NCR
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{vid}/items")
async def list_items(vid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    rows = await db.fetch("SELECT * FROM audit_visit_items WHERE visit_id=$1 ORDER BY category, created_at", vid)
    return {
        "items": [
            {
                "id": str(r["id"]),
                "category": r["category"],
                "criteria": r["criteria"],
                "severity": r["severity"],
                "result": r["result"],
                "note": r["note"],
                "photo_paths": r["photo_paths"]
                if isinstance(r["photo_paths"], list)
                else (_json.loads(r["photo_paths"]) if isinstance(r["photo_paths"], str) else []),
            }
            for r in rows
        ]
    }


@router.post("/{vid}/items")
async def add_item(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    severity = req.get("severity", "minor")
    if severity not in ("critical", "major", "minor"):
        raise HTTPException(400, "severity không hợp lệ")
    row = await db.fetchrow(
        """
        INSERT INTO audit_visit_items (visit_id, code, category, criteria, severity, clause, audit_method, documents)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
    """,
        vid,
        req.get("code", ""),
        req.get("category", ""),
        req.get("criteria", ""),
        severity,
        req.get("clause", ""),
        req.get("audit_method", ""),
        req.get("documents", ""),
    )
    return {"id": str(row["id"]), "message": "Đã thêm hạng mục"}


@router.delete("/{vid}/items/{item_id}")
async def delete_item(vid: str, item_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _validate_uuid(item_id)
    _require_provider(user)
    await db.execute("DELETE FROM audit_visit_items WHERE id=$1 AND visit_id=$2", item_id, vid)
    return {"message": "Đã xóa"}


@router.put("/{vid}/items/{item_id}")
async def update_item(vid: str, item_id: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _validate_uuid(item_id)
    _require_provider(user)
    updates, params, idx = [], [], 1
    if "result" in req:
        if req["result"] not in ("conform", "minor_nc", "major_nc", "na", "observation", None):
            raise HTTPException(400, "result không hợp lệ")
        updates.append(f"result=${idx}")
        params.append(req["result"])
        idx += 1
    for field in ["note", "evidence", "corrective_action", "corrective_status"]:
        if field in req:
            updates.append(f"{field}=${idx}")
            params.append(req[field])
            idx += 1
    if not updates:
        return {"message": "OK"}
    params.extend([item_id, vid])
    await db.execute(
        f"UPDATE audit_visit_items SET {', '.join(updates)} WHERE id=${idx} AND visit_id=${idx + 1}", *params
    )
    return {"message": "OK"}


@router.post("/{vid}/items/{item_id}/photo")
async def upload_item_photo(
    vid: str, item_id: str, file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)
):
    _validate_uuid(vid)
    _validate_uuid(item_id)
    _require_provider(user)

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Ảnh tối đa 5MB")

    save_dir = Path("docs") / "audit_photos" / vid
    save_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{item_id}_{uuid4().hex[:8]}_{file.filename or 'photo.jpg'}"
    save_path = save_dir / fname
    save_path.write_bytes(content)
    photo_url = str(save_path)

    # Append to photo_paths JSONB array
    await db.execute(
        """
        UPDATE audit_visit_items SET photo_paths = photo_paths || $1::jsonb
        WHERE id=$2 AND visit_id=$3
    """,
        _json.dumps([photo_url]),
        item_id,
        vid,
    )

    return {"message": "Đã upload ảnh", "path": photo_url}


# ── NCR CRUD ──
@router.get("/{vid}/ncr")
async def list_ncr(vid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    rows = await db.fetch("SELECT * FROM audit_ncr WHERE visit_id=$1 ORDER BY created_at", vid)
    return {
        "ncrs": [
            {
                "id": str(r["id"]),
                "description": r["description"],
                "severity": r["severity"],
                "status": r["status"],
                "corrective_action": r["corrective_action"],
                "deadline": r["deadline"].isoformat() if r["deadline"] else None,
                "photo_paths": r["photo_paths"]
                if isinstance(r["photo_paths"], list)
                else (_json.loads(r["photo_paths"]) if isinstance(r["photo_paths"], str) else []),
                "evidence_paths": r["evidence_paths"]
                if isinstance(r["evidence_paths"], list)
                else (_json.loads(r["evidence_paths"]) if isinstance(r["evidence_paths"], str) else []),
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/{vid}/ncr")
async def create_ncr(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    row = await db.fetchrow(
        """
        INSERT INTO audit_ncr (visit_id, item_id, description, severity, corrective_action, deadline)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
    """,
        vid,
        req.get("item_id"),
        req.get("description", ""),
        req.get("severity", "minor"),
        req.get("corrective_action"),
        date.fromisoformat(req["deadline"]) if req.get("deadline") else None,
    )
    return {"id": str(row["id"]), "message": "Đã tạo NCR"}


@router.put("/{vid}/ncr/{ncr_id}")
async def update_ncr(vid: str, ncr_id: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _validate_uuid(ncr_id)
    _require_provider(user)
    updates, params, idx = [], [], 1
    for field in ["description", "severity", "corrective_action", "status"]:
        if field in req:
            updates.append(f"{field}=${idx}")
            params.append(req[field])
            idx += 1
    if "deadline" in req and req["deadline"]:
        updates.append(f"deadline=${idx}")
        params.append(date.fromisoformat(req["deadline"]))
        idx += 1
    if not updates:
        return {"message": "OK"}
    params.extend([ncr_id, vid])
    await db.execute(f"UPDATE audit_ncr SET {', '.join(updates)} WHERE id=${idx} AND visit_id=${idx + 1}", *params)
    return {"message": "OK"}


@router.post("/{vid}/ncr/{ncr_id}/photo")
async def upload_ncr_photo(
    vid: str, ncr_id: str, file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)
):
    _validate_uuid(vid)
    _validate_uuid(ncr_id)
    _require_provider(user)

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Ảnh tối đa 5MB")

    save_dir = Path("docs") / "audit_photos" / vid / "ncr"
    save_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{ncr_id}_{uuid4().hex[:8]}_{file.filename or 'photo.jpg'}"
    save_path = save_dir / fname
    save_path.write_bytes(content)

    await db.execute(
        """
        UPDATE audit_ncr SET photo_paths = photo_paths || $1::jsonb WHERE id=$2 AND visit_id=$3
    """,
        _json.dumps([str(save_path)]),
        ncr_id,
        vid,
    )
    return {"message": "Đã upload ảnh NCR", "path": str(save_path)}


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE C: Report PDF Generation
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/{vid}/generate-report")
async def generate_report(vid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)

    visit = await db.fetchrow("SELECT * FROM audit_visits WHERE id=$1", vid)
    if not visit:
        raise HTTPException(404)

    items = await db.fetch("SELECT * FROM audit_visit_items WHERE visit_id=$1 ORDER BY category, created_at", vid)
    ncrs = await db.fetch("SELECT * FROM audit_ncr WHERE visit_id=$1 ORDER BY severity, created_at", vid)

    # Get names
    biz = await db.fetchrow(
        "SELECT company_name FROM users WHERE id=$1 OR (tenant_id=$1 AND is_owner=true) LIMIT 1",
        visit["business_tenant"],
    )
    biz_name = biz["company_name"] if biz else "N/A"
    provider = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", visit["provider_id"])
    provider_name = provider["company_name"] if provider else "N/A"
    auditor = (
        await db.fetchrow("SELECT company_name FROM users WHERE id=$1", visit["auditor_id"])
        if visit["auditor_id"]
        else None
    )
    auditor_name = auditor["company_name"] if auditor else "N/A"

    # Build PDF
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("VNFont", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("VNFontBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=25 * mm, bottomMargin=25 * mm, leftMargin=20 * mm, rightMargin=20 * mm
    )

    title_s = ParagraphStyle(
        "T", fontName="VNFontBold", fontSize=18, leading=24, alignment=TA_CENTER, textColor=colors.HexColor("#065E43")
    )
    sub_s = ParagraphStyle(
        "S", fontName="VNFont", fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#374151")
    )
    h2_s = ParagraphStyle("H2", fontName="VNFontBold", fontSize=12, leading=16, textColor=colors.HexColor("#1A2332"))
    body_s = ParagraphStyle("B", fontName="VNFont", fontSize=10, leading=14, textColor=colors.HexColor("#374151"))
    bold_s = ParagraphStyle("BB", fontName="VNFontBold", fontSize=10, leading=14, textColor=colors.HexColor("#1A2332"))

    elements = []
    elements.append(Paragraph("BÁO CÁO KIỂM ĐỊNH TẠI CHỖ", title_s))
    elements.append(Paragraph("ONSITE AUDIT REPORT", sub_s))
    elements.append(Spacer(1, 8 * mm))

    # Info table
    type_labels = {"initial": "Lần đầu", "renewal": "Tái đánh giá", "surprise": "Đột xuất"}
    info = [
        ["Doanh nghiệp", biz_name],
        ["Tổ chức kiểm định", provider_name],
        ["Auditor", auditor_name],
        ["Loại kiểm định", type_labels.get(visit["visit_type"], visit["visit_type"])],
        ["Ngày kiểm định", visit["scheduled_date"].strftime("%d/%m/%Y")],
        ["Địa điểm", visit["location"] or "N/A"],
    ]
    # GPS info
    start_gps = visit["start_gps"]
    end_gps = visit["end_gps"]
    if isinstance(start_gps, str):
        start_gps = _json.loads(start_gps)
    if isinstance(end_gps, str):
        end_gps = _json.loads(end_gps)
    if start_gps:
        info.append(
            ["GPS bắt đầu", f"{start_gps['lat']:.6f}, {start_gps['lng']:.6f} · {start_gps.get('timestamp', '')[:19]}"]
        )
    if end_gps:
        info.append(
            ["GPS kết thúc", f"{end_gps['lat']:.6f}, {end_gps['lng']:.6f} · {end_gps.get('timestamp', '')[:19]}"]
        )
    if start_gps and end_gps and start_gps.get("timestamp") and end_gps.get("timestamp"):
        from datetime import datetime as _dt

        try:
            t1 = _dt.fromisoformat(start_gps["timestamp"])
            t2 = _dt.fromisoformat(end_gps["timestamp"])
            duration = t2 - t1
            hours = duration.total_seconds() / 3600
            info.append(["Thời gian tại chỗ", f"{hours:.1f} giờ"])
        except Exception:
            pass
    t = Table(info, colWidths=[45 * mm, 125 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "VNFontBold"),
                ("FONTNAME", (1, 0), (1, -1), "VNFont"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    elements.append(t)
    elements.append(Spacer(1, 8 * mm))

    # Summary
    total = len(items)
    conform_count = sum(1 for i in items if i["result"] == "conform")
    minor_nc = sum(1 for i in items if i["result"] == "minor_nc")
    major_nc = sum(1 for i in items if i["result"] == "major_nc")
    obs = sum(1 for i in items if i["result"] == "observation")
    na = sum(1 for i in items if i["result"] == "na")
    answered = total - na
    score = visit["compliance_score"] or (round(conform_count / answered * 100) if answered > 0 else 0)

    elements.append(Paragraph("1. TÓM TẮT KẾT QUẢ", h2_s))
    elements.append(Spacer(1, 3 * mm))
    summary = [
        ["Tổng hạng mục", str(total)],
        ["Đạt (C)", str(conform_count)],
        ["Minor NC", str(minor_nc)],
        ["Major NC", str(major_nc)],
        ["Quan sát", str(obs)],
        ["N/A", str(na)],
        ["Điểm tuân thủ", f"{score}%"],
    ]
    st = Table(summary, colWidths=[45 * mm, 30 * mm])
    st.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "VNFont"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F7F4")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(st)
    elements.append(Spacer(1, 8 * mm))

    # Checklist detail per item
    from reportlab.platypus import Image as RLImage

    elements.append(Paragraph("2. CHI TIẾT KIỂM TRA", h2_s))
    elements.append(Spacer(1, 3 * mm))
    result_labels = {
        "conform": "Đạt (C)",
        "minor_nc": "Minor NC",
        "major_nc": "Major NC",
        "na": "N/A",
        "observation": "Quan sát",
    }

    for idx_i, item in enumerate(items, 1):
        code = item.get("code") or ""
        result_text = result_labels.get(item["result"], "—")
        sev = item["severity"]
        result_color = (
            "#087653"
            if item["result"] == "conform"
            else "#DC2626"
            if item["result"] == "major_nc"
            else "#D97706"
            if item["result"] == "minor_nc"
            else "#6B7280"
        )

        elements.append(
            Paragraph(
                f'<b>{code} — {item["criteria"]}</b> [{sev}] → <font color="{result_color}"><b>{result_text}</b></font>',
                body_s,
            )
        )

        if item.get("clause"):
            elements.append(Paragraph(f"  Điều khoản: {item['clause']}", body_s))
        if item.get("evidence"):
            elements.append(Paragraph(f"  Bằng chứng: {item['evidence']}", body_s))
        if item.get("note"):
            elements.append(Paragraph(f"  Ghi chú: {item['note']}", body_s))
        if item["result"] in ("minor_nc", "major_nc") and item.get("corrective_action"):
            elements.append(
                Paragraph(f'  <font color="#DC2626">Hành động khắc phục: {item["corrective_action"]}</font>', body_s)
            )

        # Embed photos
        photo_paths = item.get("photo_paths")
        if isinstance(photo_paths, str):
            photo_paths = _json.loads(photo_paths)
        if photo_paths:
            photo_row = []
            for pp in photo_paths[:4]:  # max 4 photos per item
                fp = Path(pp)
                if fp.exists():
                    try:
                        from PIL import Image as PILImage

                        PILImage.open(str(fp)).verify()  # validate it's a real image
                        photo_row.append(RLImage(str(fp), width=35 * mm, height=35 * mm))
                    except Exception:
                        pass
            if photo_row:
                pt = Table([photo_row], colWidths=[38 * mm] * len(photo_row))
                pt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                elements.append(pt)

        elements.append(Spacer(1, 3 * mm))

    elements.append(Spacer(1, 5 * mm))

    # NCR with photos
    if ncrs:
        elements.append(Paragraph("3. SAI PHẠM (NCR)", h2_s))
        elements.append(Spacer(1, 3 * mm))
        for n_idx, ncr in enumerate(ncrs, 1):
            sev_color = (
                "#DC2626" if ncr["severity"] == "critical" else "#D97706" if ncr["severity"] == "major" else "#6B7280"
            )
            elements.append(
                Paragraph(
                    f'<b><font color="{sev_color}">NCR #{n_idx} [{ncr["severity"].upper()}]</font></b>: {ncr["description"]}',
                    body_s,
                )
            )
            if ncr["corrective_action"]:
                elements.append(Paragraph(f"  Hành động khắc phục: {ncr['corrective_action']}", body_s))
            if ncr["deadline"]:
                elements.append(Paragraph(f"  Hạn: {ncr['deadline'].strftime('%d/%m/%Y')}", body_s))

            # NCR photos
            ncr_photos = ncr.get("photo_paths")
            if isinstance(ncr_photos, str):
                ncr_photos = _json.loads(ncr_photos)
            if ncr_photos:
                ncr_photo_row = []
                for pp in ncr_photos[:4]:
                    fp = Path(pp)
                    if fp.exists():
                        try:
                            from PIL import Image as PILImage

                            PILImage.open(str(fp)).verify()
                            ncr_photo_row.append(RLImage(str(fp), width=35 * mm, height=35 * mm))
                        except Exception:
                            pass
                if ncr_photo_row:
                    npt = Table([ncr_photo_row], colWidths=[38 * mm] * len(ncr_photo_row))
                    npt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                    elements.append(npt)
            elements.append(Spacer(1, 2 * mm))
        elements.append(Spacer(1, 6 * mm))

    # Signature area
    elements.append(Paragraph("4. XÁC NHẬN", h2_s))
    elements.append(Spacer(1, 5 * mm))
    sig = Table(
        [
            ["Auditor", "", "Đại diện doanh nghiệp"],
            ["", "", ""],
            ["_" * 25, "", "_" * 25],
            [auditor_name, "", biz_name],
        ],
        colWidths=[70 * mm, 30 * mm, 70 * mm],
    )
    sig.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "VNFont"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(sig)

    elements.append(Spacer(1, 10 * mm))
    footer_s = ParagraphStyle(
        "F", fontName="VNFont", fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor("#94A3B8")
    )
    elements.append(Paragraph(f"Báo cáo tạo tự động bởi AMINRA · {provider_name}", footer_s))

    doc.build(elements)
    buf.seek(0)

    save_dir = Path("docs") / "audit_reports"
    save_dir.mkdir(parents=True, exist_ok=True)
    pdf_file = save_dir / f"{vid}.pdf"
    pdf_file.write_bytes(buf.getvalue())

    await db.execute(
        "UPDATE audit_visits SET report_pdf_path=$1, status='report_submitted', compliance_score=$2 WHERE id=$3",
        str(pdf_file),
        score,
        vid,
    )

    log.info(f"[audit] Report generated for {vid}, score={score}")
    return {"message": "Đã tạo báo cáo", "score": score, "pdf_url": f"/api/api/audits/{vid}/report-pdf"}


@router.get("/{vid}/report-pdf")
async def download_report(vid: str, request: Request, token: Optional[str] = Query(None), db=Depends(get_db)):
    _validate_uuid(vid)
    from auth.jwt_utils import decode_token

    auth = request.headers.get("Authorization", "")
    tk = auth[7:] if auth.startswith("Bearer ") else token
    if not tk:
        raise HTTPException(401)
    try:
        decode_token(tk)
    except:
        raise HTTPException(401)

    row = await db.fetchrow("SELECT report_pdf_path FROM audit_visits WHERE id=$1", vid)
    if not row or not row["report_pdf_path"]:
        raise HTTPException(404, "Báo cáo chưa được tạo")

    pdf = Path(row["report_pdf_path"])
    if not pdf.exists():
        raise HTTPException(404, "File không tồn tại")

    return Response(
        content=pdf.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="audit_report_{vid[:8]}.pdf"'},
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE D: History + Cert Decision
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/history/{business_tenant}")
async def visit_history(business_tenant: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(business_tenant)
    _require_provider(user)
    rows = await db.fetch(
        """
        SELECT v.*, a.company_name AS auditor_name
        FROM audit_visits v LEFT JOIN users a ON a.id = v.auditor_id
        WHERE v.business_tenant=$1 AND v.provider_id=$2
        ORDER BY v.scheduled_date DESC
    """,
        business_tenant,
        user.get("tenant_id") or user["sub"],
    )
    return {
        "history": [
            {
                "id": str(r["id"]),
                "visit_type": r["visit_type"],
                "status": r["status"],
                "scheduled_date": r["scheduled_date"].isoformat(),
                "compliance_score": r["compliance_score"],
                "auditor_name": r["auditor_name"],
                "has_report": bool(r["report_pdf_path"]),
            }
            for r in rows
        ]
    }


@router.post("/{vid}/decision")
async def cert_decision(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    """Provider decides on cert state after a visit.

    Fixes from bug audit 2026-04-26:
      C4 — filter by issued_by so we don't stomp other providers' certs
      W4-M1 — route revoke through cert_lifecycle.revoke_cert (audit log + reason)
    """
    _validate_uuid(vid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")

    decision = req.get("decision")
    if decision not in ("renew", "suspend", "revoke"):
        raise HTTPException(400, "decision: renew | suspend | revoke")

    visit = await db.fetchrow("SELECT business_tenant, provider_id FROM audit_visits WHERE id=$1", vid)
    if not visit:
        raise HTTPException(404)
    provider_id = user.get("tenant_id") or user["sub"]
    # Cross-check the visit belongs to this CB.
    if str(visit["provider_id"]) != str(provider_id):
        raise HTTPException(403, "Visit không thuộc tổ chức của bạn")

    notes = req.get("notes", "") or ""
    decision_labels = {"renew": "gia hạn", "suspend": "tạm đình chỉ", "revoke": "thu hồi"}

    if decision == "revoke":
        # W4-M1 — go through proper lifecycle helper that sets revoked_at +
        # revocation_reason + revoked_by + writes audit log.
        if not notes.strip():
            raise HTTPException(400, "Phải nhập lý do khi thu hồi chứng nhận")
        from services.cert_lifecycle import revoke_active_certs_for_business

        revoker_id = await resolve_canonical_user_id(user, db)
        affected = await revoke_active_certs_for_business(
            db,
            business_tenant=str(visit["business_tenant"]),
            issued_by=str(provider_id),
            reason=notes.strip(),
            revoked_by=str(revoker_id) if revoker_id else None,
        )
        log.info(f"[audit] {affected} cert(s) revoked for {visit['business_tenant']} by {provider_id}")
    else:
        # C4 — restrict update to certs issued by THIS provider only.
        cert_status = {"renew": "active", "suspend": "suspended"}[decision]
        await db.execute(
            "UPDATE halal_certificates SET status=$1, updated_at=NOW() "
            "WHERE business_tenant=$2 AND issued_by=$3 AND status <> 'revoked'",
            cert_status,
            visit["business_tenant"],
            provider_id,
        )
        await log_audit(
            db,
            user=user,
            action=f"certificate.{decision}",
            entity_type="certificate",
            metadata={"business_tenant": str(visit["business_tenant"]), "notes": notes},
        )

    biz_owner = await db.fetchrow(
        "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1",
        visit["business_tenant"],
    )
    if biz_owner:
        await notify(
            db,
            str(biz_owner["id"]),
            "certificate",
            f"Chứng nhận đã được {decision_labels[decision]}",
            notes,
            "/documents",
        )

    log.info(f"[audit] Decision {decision} for business {visit['business_tenant']}")
    return {"message": f"Đã {decision_labels[decision]} chứng nhận"}


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE F: Signature + GPS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/{vid}/signature")
async def upload_signature(
    vid: str,
    file: UploadFile = File(...),
    type: str = Query("auditor"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    _validate_uuid(vid)
    _require_provider(user)
    if type not in ("auditor", "business"):
        raise HTTPException(400)

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Chữ ký tối đa 2MB")

    save_dir = Path("docs") / "signatures"
    save_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{vid}_{type}.png"
    save_path = save_dir / fname
    save_path.write_bytes(content)

    col = "auditor_signature_path" if type == "auditor" else "business_signature_path"
    await db.execute(f"UPDATE audit_visits SET {col}=$1 WHERE id=$2", str(save_path), vid)
    return {"message": "Đã lưu chữ ký"}


@router.put("/{vid}/gps")
async def save_gps(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(vid)
    _require_provider(user)
    gps_type = req.get("type")  # start | end
    if gps_type not in ("start", "end"):
        raise HTTPException(400)
    gps_data = _json.dumps({"lat": req.get("lat"), "lng": req.get("lng"), "timestamp": datetime.utcnow().isoformat()})
    col = "start_gps" if gps_type == "start" else "end_gps"
    await db.execute(f"UPDATE audit_visits SET {col}=$1::jsonb WHERE id=$2", gps_data, vid)
    return {"message": "OK"}


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE H: Follow-up & Corrective Action
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/ncr/pending")
async def pending_ncr(user=Depends(get_current_user), db=Depends(get_db)):
    """Business sees their open NCRs."""
    if user.get("role") != "business":
        raise HTTPException(403)
    rows = await db.fetch(
        """
        SELECT n.*, v.scheduled_date, v.location
        FROM audit_ncr n
        JOIN audit_visits v ON v.id = n.visit_id
        WHERE v.business_tenant=$1 AND n.status != 'closed'
        ORDER BY n.deadline ASC NULLS LAST
    """,
        user.get("tenant_id"),
    )
    return {
        "ncrs": [
            {
                "id": str(r["id"]),
                "visit_id": str(r["visit_id"]),
                "description": r["description"],
                "severity": r["severity"],
                "corrective_action": r["corrective_action"],
                "deadline": r["deadline"].isoformat() if r["deadline"] else None,
                "status": r["status"],
                "scheduled_date": r["scheduled_date"].isoformat(),
                "location": r["location"],
            }
            for r in rows
        ]
    }


@router.post("/ncr/{ncr_id}/evidence")
async def upload_ncr_evidence(
    ncr_id: str, file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)
):
    """Business uploads corrective action evidence."""
    _validate_uuid(ncr_id)
    if user.get("role") != "business":
        raise HTTPException(403)

    # Verify NCR belongs to business
    ncr = await db.fetchrow(
        """
        SELECT n.id, n.visit_id FROM audit_ncr n
        JOIN audit_visits v ON v.id = n.visit_id
        WHERE n.id=$1 AND v.business_tenant=$2
    """,
        ncr_id,
        user.get("tenant_id"),
    )
    if not ncr:
        raise HTTPException(404)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File tối đa 10MB")

    save_dir = Path("docs") / "ncr_evidence" / str(ncr["visit_id"])
    save_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{ncr_id}_{uuid4().hex[:8]}_{file.filename or 'evidence'}"
    save_path = save_dir / fname
    save_path.write_bytes(content)

    await db.execute(
        """
        UPDATE audit_ncr SET evidence_paths = evidence_paths || $1::jsonb, status='in_review'
        WHERE id=$2
    """,
        _json.dumps([str(save_path)]),
        ncr_id,
    )

    # Notify auditor
    visit = await db.fetchrow("SELECT auditor_id, provider_id FROM audit_visits WHERE id=$1", ncr["visit_id"])
    if visit and visit["auditor_id"]:
        await notify(
            db,
            str(visit["auditor_id"]),
            "audit",
            "Doanh nghiệp đã gửi bằng chứng khắc phục",
            f"NCR #{ncr_id[:8]}",
            "/audits",
        )

    return {"message": "Đã upload bằng chứng"}


@router.put("/ncr/{ncr_id}/verify")
async def verify_ncr(ncr_id: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    """Auditor verifies NCR evidence and closes it."""
    _validate_uuid(ncr_id)
    _require_provider(user)

    action = req.get("action")  # close | reject
    if action not in ("close", "reject"):
        raise HTTPException(400, "action: close | reject")

    if action == "close":
        closer_id = await resolve_canonical_user_id(user, db)
        await db.execute(
            "UPDATE audit_ncr SET status='closed', closed_at=NOW(), closed_by=$1 WHERE id=$2", closer_id, ncr_id
        )
    else:
        await db.execute("UPDATE audit_ncr SET status='open' WHERE id=$1", ncr_id)

    # Notify business
    ncr = await db.fetchrow(
        """
        SELECT v.business_tenant FROM audit_ncr n JOIN audit_visits v ON v.id = n.visit_id WHERE n.id=$1
    """,
        ncr_id,
    )
    if ncr:
        biz_owner = await db.fetchrow(
            "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", ncr["business_tenant"]
        )
        if biz_owner:
            msg = "NCR đã được đóng — đạt yêu cầu" if action == "close" else "NCR cần bổ sung bằng chứng"
            await notify(db, str(biz_owner["id"]), "audit", msg, "", "/audits")

    return {"message": "Đã xác nhận" if action == "close" else "Yêu cầu bổ sung"}


@router.post("/{vid}/follow-up")
async def create_follow_up(vid: str, req: dict, user=Depends(get_current_user), db=Depends(get_db)):
    """Create a follow-up visit linked to parent."""
    _validate_uuid(vid)
    _require_provider(user)
    if not user.get("is_owner"):
        raise HTTPException(403)

    parent = await db.fetchrow(
        "SELECT business_tenant, provider_id, auditor_id, template_id FROM audit_visits WHERE id=$1", vid
    )
    if not parent:
        raise HTTPException(404)

    row = await db.fetchrow(
        """
        INSERT INTO audit_visits (business_tenant, provider_id, auditor_id, template_id, visit_type, scheduled_date, location, notes)
        VALUES ($1, $2, $3, $4, 'renewal', $5, $6, $7) RETURNING id
    """,
        parent["business_tenant"],
        parent["provider_id"],
        parent["auditor_id"],
        parent["template_id"],
        date.fromisoformat(req.get("scheduled_date", date.today().isoformat())),
        req.get("location", ""),
        f"Follow-up từ kiểm định {vid[:8]}",
    )

    return {"id": str(row["id"]), "message": "Đã tạo chuyến kiểm định follow-up"}
