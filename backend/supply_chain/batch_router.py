"""Production batch CRUD + step tracking + QR generation."""

import logging
import os
import json as _json
import io
import time
from uuid import UUID as _UUID, uuid4
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Request
from fastapi.responses import Response
from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.permissions import check_permission_db
from .models import BatchCreate, BatchUpdate, BatchStepUpdate, BatchOut
from .eligibility_service import assert_supplier_eligible

log = logging.getLogger("aminra.supply_chain.batches")
router = APIRouter()

# Public trace is immutable after seal, but a short TTL avoids long-lived stale
# reads if an operator disables public_trace_enabled after publication. This
# cache absorbs short high-concurrency bursts on QR/public trace pages without
# weakening the DB as source of truth for longer windows.
_PUBLIC_TRACE_CACHE_TTL_SECONDS = float(os.getenv("PUBLIC_TRACE_CACHE_TTL_SECONDS", "5"))
_PUBLIC_TRACE_CACHE_MAX_ITEMS = int(os.getenv("PUBLIC_TRACE_CACHE_MAX_ITEMS", "512"))
_PUBLIC_TRACE_RESPONSE_CACHE: dict[str, tuple[float, str]] = {}

# Base URL for QR trace links — uses FRONTEND_URL env or falls back to request origin
_FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")


def _trace_url(public_trace_id: str, request: Request | None = None) -> str:
    """Build public trace URL from env or request origin.

    Public URLs must use the opaque globally-unique trace id, never tenant-local
    `batch_code`; batch_code is a business label and can collide by tenant.
    """
    base = _FRONTEND_URL
    if not base and request:
        origin = request.headers.get("origin") or request.headers.get("referer", "")
        if origin:
            # Extract scheme + host from origin/referer
            from urllib.parse import urlparse

            p = urlparse(origin)
            base = f"{p.scheme}://{p.netloc}" if p.netloc else ""
    if not base:
        base = "https://aminra.app"
    return f"{base}/trace/{public_trace_id}"


def _validate_uuid(v: str) -> str:
    try:
        _UUID(v)
    except ValueError:
        raise HTTPException(400, "Invalid ID")
    return v


def _require_business(user: dict):
    if user.get("role") != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")
    return user.get("tenant_id")


def _generate_batch_code() -> str:
    now = datetime.utcnow()
    return f"LOT-{now.strftime('%Y%m%d')}-{str(uuid4())[:6].upper()}"


def _json_obj(value):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return _json.loads(value)
    return dict(value)


def _json_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return _json.loads(value)
    return list(value)


def _record_get(row, key: str, default=None):
    return row[key] if row is not None and key in row.keys() else default


def _canonical_json(data: dict) -> str:
    return _json.dumps(data, sort_keys=True, ensure_ascii=False)


def _integrity_hash(data: dict) -> str:
    import hashlib

    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


async def assert_batch_mutable(db, batch_id: str, tenant_id: str) -> None:
    row = await db.fetchrow(
        "SELECT integrity_hash FROM production_batches WHERE id=$1 AND tenant_id=$2",
        batch_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(404)
    if _record_get(row, "integrity_hash"):
        raise HTTPException(403, "Lô hàng đã được seal — không thể thay đổi")


def _checklist_complete(checklist) -> bool:
    for item in _json_list(checklist):
        if isinstance(item, dict) and item.get("checked") is not True:
            return False
    return True


def _checklist_requires_photo(checklist) -> bool:
    for item in _json_list(checklist):
        if isinstance(item, dict) and (
            item.get("requires_photo") or item.get("photo_required") or item.get("requires_evidence") or item.get("evidence_required")
        ):
            return True
    return False


# ── CRUD Batches ──────────────────────────────────────────────────────────────


@router.get("/batches")
async def list_batches(
    status: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    period: Optional[str] = Query(None),  # today, week, month
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    tenant_id = _require_business(user)
    cond = "WHERE b.tenant_id = $1"
    params: list = [tenant_id]
    idx = 2

    if status:
        cond += f" AND b.status = ${idx}"
        params.append(status)
        idx += 1
    if product:
        cond += f" AND b.product_name ILIKE ${idx}"
        params.append(f"%{product}%")
        idx += 1
    if period == "today":
        cond += " AND b.created_at::date = CURRENT_DATE"
    elif period == "week":
        cond += " AND b.created_at >= NOW() - INTERVAL '7 days'"
    elif period == "month":
        cond += " AND b.created_at >= NOW() - INTERVAL '30 days'"

    rows = await db.fetch(
        f"""
        SELECT b.*,
            p.name AS process_name,
            (SELECT COUNT(*) FROM batch_steps s WHERE s.batch_id = b.id) AS step_count,
            (SELECT COUNT(*) FROM batch_steps s WHERE s.batch_id = b.id AND s.status = 'completed') AS step_completed,
            (SELECT COUNT(*) FROM batch_materials m WHERE m.batch_id = b.id) AS material_count
        FROM production_batches b
        LEFT JOIN process_templates p ON p.id = b.process_template_id
        {cond}
        ORDER BY b.created_at DESC
    """,
        *params,
    )

    return {
        "batches": [
            BatchOut(
                id=str(r["id"]),
                batch_code=r["batch_code"],
                public_trace_id=str(r["public_trace_id"]) if _record_get(r, "public_trace_id") else None,
                public_trace_enabled=bool(_record_get(r, "public_trace_enabled")),
                product_name=r["product_name"],
                process_template_id=str(r["process_template_id"]) if r["process_template_id"] else None,
                process_name=r["process_name"],
                status=r["status"],
                started_at=r["started_at"],
                completed_at=r["completed_at"],
                compliance_score=r["compliance_score"],
                qr_code_url=r["qr_code_url"],
                notes=r["notes"],
                step_count=r["step_count"],
                step_completed=r["step_completed"],
                material_count=r["material_count"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    }


@router.post("/batches")
async def create_batch(req: BatchCreate, user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    batch_code = req.batch_code or _generate_batch_code()
    process_id = req.process_template_id
    if process_id:
        _validate_uuid(process_id)
        # Cross-tenant guard: process must belong to caller. Without this check,
        # one tenant could attach another tenant's process template, leaking
        # IP and breaking traceability assumptions.
        owns_proc = await db.fetchval(
            "SELECT 1 FROM process_templates WHERE id=$1 AND tenant_id=$2",
            process_id, tenant_id,
        )
        if not owns_proc:
            raise HTTPException(400, "Quy trình không tồn tại")

    # Pre-validate materials before inserting batch (fail fast, no orphan rows).
    material_eligibility: dict[str, dict] = {}
    if req.materials:
        for m in req.materials:
            _validate_uuid(m["material_id"])
            mat = await db.fetchrow(
                "SELECT id, supplier_id, category FROM materials WHERE id=$1 AND tenant_id=$2",
                m["material_id"], tenant_id,
            )
            if not mat:
                raise HTTPException(400, f"Nguyên liệu không tồn tại: {m['material_id']}")
            eligibility = await assert_supplier_eligible(db, str(tenant_id), str(mat["supplier_id"]), mat["category"])
            material_eligibility[m["material_id"]] = {
                "supplier_id": str(mat["supplier_id"]),
                "eligibility_id": eligibility.certificate_id,
                "eligibility_snapshot": {
                    "supplier_id": str(mat["supplier_id"]),
                    "eligibility_id": eligibility.certificate_id,
                    "status": eligibility.status,
                    "valid_from": eligibility.valid_from.isoformat() if eligibility.valid_from else None,
                    "valid_until": eligibility.valid_until.isoformat() if eligibility.valid_until else None,
                    "source_of_truth": eligibility.source_of_truth,
                    "scope": eligibility.scope,
                    "checked_at": datetime.utcnow().isoformat() + "Z",
                },
            }

    row = await db.fetchrow(
        """
        INSERT INTO production_batches (tenant_id, batch_code, product_name, process_template_id, notes)
        VALUES ($1,$2,$3,$4,$5) RETURNING id, public_trace_id
    """,
        tenant_id,
        batch_code,
        req.product_name,
        process_id,
        req.notes,
    )

    batch_id = str(row["id"])

    # Link materials (already validated above)
    if req.materials:
        for m in req.materials:
            await db.execute(
                """
                INSERT INTO batch_materials (batch_id, material_id, quantity, unit, supplier_id, eligibility_id, eligibility_snapshot)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
            """,
                batch_id,
                m["material_id"],
                m.get("quantity"),
                _record_get(m, "unit"),
                material_eligibility[m["material_id"]]["supplier_id"],
                material_eligibility[m["material_id"]]["eligibility_id"],
                _json.dumps(material_eligibility[m["material_id"]]["eligibility_snapshot"]),
            )

    # Auto-create steps from process template
    if process_id:
        pt = await db.fetchrow(
            "SELECT flowchart FROM process_templates WHERE id=$1 AND tenant_id=$2", process_id, tenant_id
        )
        if pt and pt["flowchart"]:
            fc = pt["flowchart"] if isinstance(pt["flowchart"], dict) else _json.loads(pt["flowchart"])
            nodes = fc.get("nodes", [])
            for node in sorted(nodes, key=lambda n: n.get("order", 0)):
                checklist = _json.dumps([{"text": item, "checked": False} for item in (node.get("checklist") or [])])
                await db.execute(
                    """
                    INSERT INTO batch_steps (batch_id, node_id, step_name, checklist)
                    VALUES ($1,$2,$3,$4::jsonb)
                """,
                    batch_id,
                    node["id"],
                    node.get("label", "Bước"),
                    checklist,
                )

    log.info(f"[batches] Created {batch_code}")
    return {
        "id": batch_id,
        "batch_code": batch_code,
        "public_trace_id": str(row["public_trace_id"]),
        "message": "Đã tạo lô hàng",
    }


@router.get("/batches/stats")
async def batch_stats(user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    total = await db.fetchval("SELECT COUNT(*) FROM production_batches WHERE tenant_id=$1", tenant_id)
    completed = await db.fetchval(
        "SELECT COUNT(*) FROM production_batches WHERE tenant_id=$1 AND status='completed'", tenant_id
    )
    in_progress = await db.fetchval(
        "SELECT COUNT(*) FROM production_batches WHERE tenant_id=$1 AND status='in_progress'", tenant_id
    )
    draft = await db.fetchval(
        "SELECT COUNT(*) FROM production_batches WHERE tenant_id=$1 AND status='draft'", tenant_id
    )
    return {"total": total, "completed": completed, "in_progress": in_progress, "draft": draft}


@router.get("/batches/members")
async def list_tenant_members(user=Depends(get_current_user), db=Depends(get_db)):
    """List all members in the same tenant for assignment."""
    tenant_id = _require_business(user)
    rows = await db.fetch(
        "SELECT id, email, company_name, is_owner, ihc_role FROM users WHERE tenant_id=$1 AND status='active' ORDER BY is_owner DESC, company_name",
        tenant_id,
    )
    return {
        "members": [
            {
                "id": str(r["id"]),
                "name": r["company_name"],
                "email": r["email"],
                "is_owner": r["is_owner"],
                "role": r["ihc_role"] or ("Chủ tài khoản" if r["is_owner"] else "Thành viên"),
            }
            for r in rows
        ]
    }


@router.get("/batches/trace/{trace_id}")
async def public_trace(trace_id: str, db=Depends(get_db)):
    """Public endpoint — no auth. Returns verified trace info for a sealed batch.

    `trace_id` is the opaque public_trace_id. Business `batch_code` is not a
    public lookup key because it is only tenant-scoped.
    """
    try:
        _UUID(trace_id)
    except ValueError:
        raise HTTPException(404, "Không tìm thấy truy xuất")

    now = time.monotonic()
    cached = _PUBLIC_TRACE_RESPONSE_CACHE.get(trace_id)
    if cached and cached[0] > now:
        return Response(
            content=cached[1],
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=5, stale-while-revalidate=30"},
        )

    row = await db.fetchrow(
        """
        SELECT b.public_trace_id, b.batch_code, b.status, b.integrity_hash,
               b.sealed_data::text AS sealed_text, b.public_trace_enabled,
               b.approved_at, b.approved_by
        FROM production_batches b
        WHERE b.public_trace_id = $1
    """,
        trace_id,
    )
    if not row:
        raise HTTPException(404, "Không tìm thấy truy xuất")

    if (
        row["status"] != "completed"
        or not _record_get(row, "integrity_hash")
        or not _record_get(row, "sealed_text")
        or not _record_get(row, "public_trace_enabled")
    ):
        raise HTTPException(404, "Lô hàng chưa sẵn sàng để truy xuất")

    sealed = _json.loads(row["sealed_text"])
    computed = _integrity_hash(sealed)
    integrity = {
        "sealed": True,
        "verified": computed == row["integrity_hash"],
        "hash": row["integrity_hash"],
        "computed_hash": computed,
        "sealed_at": sealed.get("approved_at") or str(_record_get(row, "approved_at") or ""),
        "sealed_by": sealed.get("approved_by") or _record_get(row, "approved_by") or "",
        "algorithm": sealed.get("hash_algorithm", "sha256"),
        "snapshot_version": sealed.get("snapshot_version", 1),
    }

    steps = sealed.get("steps") or []
    materials = sealed.get("materials") or []
    certificates = sealed.get("certificates") or []
    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.get("status") == "completed")
    batch = sealed.get("batch") or {}
    process = sealed.get("process") or {}
    company = sealed.get("company") or {}

    payload = {
        "batch": {
            "batch_code": batch.get("batch_code") or sealed.get("batch_code") or row["batch_code"],
            "product_name": batch.get("product_name") or sealed.get("product_name"),
            "status": batch.get("status") or row["status"],
            "company_name": company.get("name") or sealed.get("company_name") or "N/A",
            "process_name": process.get("name"),
            "process_description": process.get("description"),
            "started_at": batch.get("started_at") or sealed.get("started_at"),
            "completed_at": batch.get("completed_at") or sealed.get("completed_at"),
            "compliance_score": batch.get("compliance_score", sealed.get("compliance_score")),
            "created_at": batch.get("created_at") or sealed.get("created_at"),
            "public_trace_id": str(row["public_trace_id"]),
        },
        "integrity": integrity,
        "progress": {
            "total": total_steps,
            "completed": completed_steps,
            "percent": round(completed_steps / total_steps * 100) if total_steps else 0,
        },
        "steps": [
            {
                "name": s.get("step_name") or s.get("name"),
                "performed_by": s.get("performed_by"),
                "started_at": s.get("started_at"),
                "completed_at": s.get("completed_at"),
                "status": s.get("status"),
                "approved_by": s.get("approved_by"),
            }
            for s in steps
        ],
        "materials": [
            {
                "name": m.get("material_name") or m.get("name"),
                "sku": _record_get(m, "sku"),
                "category": _record_get(m, "category"),
                "halal_risk": _record_get(m, "halal_risk") or "unknown",
                "supplier_name": _record_get(m, "supplier_name"),
                "supplier_verified": (_record_get(m, "eligibility_snapshot") or {}).get("status") == "active",
                "quantity": str(m.get("quantity")) if m.get("quantity") is not None else None,
                "unit": _record_get(m, "unit"),
            }
            for m in materials
        ],
        "certificates": certificates,
    }
    body = _json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if _PUBLIC_TRACE_CACHE_TTL_SECONDS > 0:
        if len(_PUBLIC_TRACE_RESPONSE_CACHE) >= _PUBLIC_TRACE_CACHE_MAX_ITEMS:
            # Drop expired items first; if still full, evict an arbitrary oldest
            # inserted item. This keeps the hot-path O(1) for normal use.
            expired = [k for k, (expires, _) in _PUBLIC_TRACE_RESPONSE_CACHE.items() if expires <= now]
            for k in expired:
                _PUBLIC_TRACE_RESPONSE_CACHE.pop(k, None)
            if len(_PUBLIC_TRACE_RESPONSE_CACHE) >= _PUBLIC_TRACE_CACHE_MAX_ITEMS:
                _PUBLIC_TRACE_RESPONSE_CACHE.pop(next(iter(_PUBLIC_TRACE_RESPONSE_CACHE)), None)
        _PUBLIC_TRACE_RESPONSE_CACHE[trace_id] = (now + _PUBLIC_TRACE_CACHE_TTL_SECONDS, body)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=5, stale-while-revalidate=30"},
    )


@router.put("/batches/{bid}/assign-member")
async def assign_member_to_batch(bid: str, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    """Owner assigns a member to approve the batch."""
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    if not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tài khoản mới có thể ủy quyền")

    await assert_batch_mutable(db, bid, tenant_id)

    body = await request.json()
    member_id = body.get("member_id")
    if not member_id:
        raise HTTPException(400, "Thiếu member_id")

    _validate_uuid(member_id)
    member = await db.fetchrow(
        "SELECT id, company_name, email FROM users WHERE id=$1 AND tenant_id=$2 AND status='active'",
        member_id,
        tenant_id,
    )
    if not member:
        raise HTTPException(404, "Thành viên không tồn tại trong tổ chức")

    await db.execute(
        "UPDATE production_batches SET assigned_to=$1, assigned_name=$2 WHERE id=$3",
        member_id,
        member["company_name"],
        bid,
    )

    log.info(f"[batches] Assigned {bid} to {member['company_name']}")
    return {"message": f"Đã ủy quyền cho {member['company_name']}", "assigned_name": member["company_name"]}


@router.get("/batches/{bid}")
async def get_batch(bid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    row = await db.fetchrow(
        """
        SELECT b.*, p.name AS process_name
        FROM production_batches b
        LEFT JOIN process_templates p ON p.id = b.process_template_id
        WHERE b.id=$1 AND b.tenant_id=$2
    """,
        bid,
        tenant_id,
    )
    if not row:
        raise HTTPException(404)

    # Get steps
    steps = await db.fetch("SELECT * FROM batch_steps WHERE batch_id=$1 ORDER BY created_at", bid)

    # Get materials
    mats = await db.fetch(
        """
        SELECT bm.*, m.name AS material_name, m.sku, s.name AS supplier_name
        FROM batch_materials bm
        JOIN materials m ON m.id = bm.material_id
        LEFT JOIN suppliers s ON s.id = m.supplier_id
        WHERE bm.batch_id=$1
    """,
        bid,
    )

    return {
        "batch": dict(row),
        "steps": [dict(s) for s in steps],
        "materials": [dict(m) for m in mats],
    }


# Batch lifecycle: draft → in_progress → {completed | rejected} (terminal).
# Self-transitions (X → X) are silently allowed for idempotent PUTs.
_BATCH_TRANSITIONS = {
    "draft": {"in_progress", "rejected"},
    "in_progress": {"completed", "rejected"},
    "completed": set(),  # terminal
    "rejected": set(),   # terminal
}


def _validate_batch_transition(from_status: str, to_status: str) -> None:
    if from_status == to_status:
        return
    allowed = _BATCH_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise HTTPException(
            409,
            f"Chuyển trạng thái không hợp lệ: {from_status} → {to_status}. "
            f"Cho phép từ '{from_status}': {sorted(allowed) or 'không có (terminal)'}",
        )


@router.put("/batches/{bid}")
async def update_batch(bid: str, req: BatchUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    await assert_batch_mutable(db, bid, tenant_id)
    updates, params, idx = [], [bid, tenant_id], 3

    if req.product_name is not None:
        updates.append(f"product_name = ${idx}")
        params.append(req.product_name)
        idx += 1
    if req.status is not None:
        # Validate transition against current status before mutating.
        prev_status = await db.fetchval(
            "SELECT status FROM production_batches WHERE id=$1 AND tenant_id=$2",
            bid, tenant_id,
        )
        if prev_status is None:
            raise HTTPException(404)
        _validate_batch_transition(prev_status, req.status)

        updates.append(f"status = ${idx}")
        params.append(req.status)
        idx += 1
        if req.status == "in_progress":
            updates.append("started_at = NOW()")
        elif req.status in ("completed", "rejected"):
            updates.append("completed_at = NOW()")
    if req.notes is not None:
        updates.append(f"notes = ${idx}")
        params.append(req.notes)
        idx += 1

    if not updates:
        return {"message": "Không có thay đổi"}
    result = await db.execute(
        f"UPDATE production_batches SET {', '.join(updates)} WHERE id=$1 AND tenant_id=$2",
        *params,
    )
    if result == "UPDATE 0":
        raise HTTPException(404)
    return {"message": "Đã cập nhật"}


@router.delete("/batches/{bid}")
async def delete_batch(bid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_delete")
    await assert_batch_mutable(db, bid, tenant_id)
    result = await db.execute("DELETE FROM production_batches WHERE id=$1 AND tenant_id=$2", bid, tenant_id)
    if result == "DELETE 0":
        raise HTTPException(404)
    return {"message": "Đã xoá"}


# ── Step tracking ─────────────────────────────────────────────────────────────


@router.put("/batches/{bid}/steps/{step_id}")
async def update_step(bid: str, step_id: str, req: BatchStepUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(bid)
    _validate_uuid(step_id)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")

    # Verify batch belongs to tenant + not sealed
    await assert_batch_mutable(db, bid, tenant_id)

    updates, params, idx = [], [step_id, bid], 3
    if req.status is not None:
        updates.append(f"status = ${idx}")
        params.append(req.status)
        idx += 1
        if req.status == "in_progress":
            updates.append("started_at = NOW()")
        elif req.status == "completed":
            updates.append("completed_at = NOW()")
    if req.performed_by is not None:
        updates.append(f"performed_by = ${idx}")
        params.append(req.performed_by)
        idx += 1
    if req.notes is not None:
        updates.append(f"notes = ${idx}")
        params.append(req.notes)
        idx += 1
    if req.checklist is not None:
        updates.append(f"checklist = ${idx}::jsonb")
        params.append(_json.dumps(req.checklist))
        idx += 1

    if not updates:
        return {"message": "Không có thay đổi"}
    await db.execute(f"UPDATE batch_steps SET {', '.join(updates)} WHERE id=$1 AND batch_id=$2", *params)

    # Recalculate compliance score
    total = await db.fetchval("SELECT COUNT(*) FROM batch_steps WHERE batch_id=$1", bid)
    done = await db.fetchval("SELECT COUNT(*) FROM batch_steps WHERE batch_id=$1 AND status='completed'", bid)
    score = round((done / total) * 100) if total > 0 else 0
    await db.execute("UPDATE production_batches SET compliance_score=$1 WHERE id=$2", score, bid)

    return {"message": "Đã cập nhật", "compliance_score": score}


@router.post("/batches/{bid}/steps/{step_id}/approve")
async def approve_step(bid: str, step_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Owner or assigned member approves a completed step."""
    _validate_uuid(bid)
    _validate_uuid(step_id)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_approve")
    b = await db.fetchrow("SELECT id, assigned_to, integrity_hash FROM production_batches WHERE id=$1 AND tenant_id=$2", bid, tenant_id)
    if not b:
        raise HTTPException(404)
    if _record_get(b, "integrity_hash"):
        raise HTTPException(403, "Lô hàng đã được seal — không thể thay đổi")
    # Allow: owner OR assigned member
    if not user.get("is_owner") and str(_record_get(b, "assigned_to")) != user.get("sub"):
        raise HTTPException(403, "Bạn chưa được ủy quyền xác nhận lô hàng này")

    step = await db.fetchrow("SELECT status FROM batch_steps WHERE id=$1 AND batch_id=$2", step_id, bid)
    if not step:
        raise HTTPException(404)
    if step["status"] != "completed":
        raise HTTPException(400, "Chỉ có thể xác nhận bước đã hoàn thành")

    approver = user.get("email", "admin")
    await db.execute("UPDATE batch_steps SET approved_by=$1, approved_at=NOW() WHERE id=$2", approver, step_id)
    return {"message": "Đã xác nhận bước"}


@router.post("/batches/{bid}/approve")
async def approve_batch(bid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Owner or assigned member approves batch — seals all data + computes integrity hash."""
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_approve")
    row = await db.fetchrow(
        """
        SELECT b.*, p.name AS process_name, p.description AS process_description,
               p.version AS process_version, u.company_name
        FROM production_batches b
        LEFT JOIN process_templates p ON p.id = b.process_template_id
        LEFT JOIN users u ON u.id = b.tenant_id
        WHERE b.id=$1 AND b.tenant_id=$2
        """,
        bid,
        tenant_id,
    )
    if not row:
        raise HTTPException(404)
    # Allow: owner OR assigned member
    if not user.get("is_owner") and str(_record_get(row, "assigned_to")) != user.get("sub"):
        raise HTTPException(403, "Bạn chưa được ủy quyền xác nhận lô hàng này")
    if row["status"] != "completed":
        raise HTTPException(400, "Lô hàng chưa hoàn thành")
    if _record_get(row, "integrity_hash"):
        raise HTTPException(400, "Lô hàng đã được seal — không thể thay đổi")

    # Collect all data for sealing
    steps = await db.fetch("SELECT * FROM batch_steps WHERE batch_id=$1 ORDER BY created_at", bid)
    materials = await db.fetch(
        """
        SELECT bm.*, m.name AS material_name, m.sku, m.category, m.halal_risk,
               COALESCE(bm.supplier_id, m.supplier_id) AS effective_supplier_id,
               s.name AS supplier_name
        FROM batch_materials bm
        JOIN materials m ON m.id = bm.material_id
        LEFT JOIN suppliers s ON s.id = COALESCE(bm.supplier_id, m.supplier_id)
        WHERE bm.batch_id=$1
    """,
        bid,
    )
    certs = await db.fetch(
        """
        SELECT DISTINCT sc.cert_type, sc.cert_number, sc.issuing_body,
               sc.issued_date, sc.expiry_date, s.name AS supplier_name
        FROM batch_materials bm
        JOIN materials m ON m.id = bm.material_id
        JOIN suppliers s ON s.id = COALESCE(bm.supplier_id, m.supplier_id)
        JOIN supplier_certificates sc ON sc.supplier_id = s.id
        WHERE bm.batch_id=$1
        ORDER BY sc.expiry_date DESC
        """,
        bid,
    )

    readiness_errors: list[str] = []
    for s in steps:
        if s["status"] != "completed":
            readiness_errors.append(f"Bước '{s['step_name']}' chưa hoàn thành")
        if not _record_get(s, "approved_by") or not _record_get(s, "approved_at"):
            readiness_errors.append(f"Bước '{s['step_name']}' chưa được xác nhận")
        if not _checklist_complete(_record_get(s, "checklist")):
            readiness_errors.append(f"Checklist của bước '{s['step_name']}' chưa hoàn tất")
        if _checklist_requires_photo(_record_get(s, "checklist")) and not _record_get(s, "photo_path"):
            readiness_errors.append(f"Bước '{s['step_name']}' thiếu bằng chứng/ảnh bắt buộc")

    material_snapshots: list[dict] = []
    for m in materials:
        supplier_id = str(m["effective_supplier_id"]) if _record_get(m, "effective_supplier_id") else None
        if not supplier_id:
            readiness_errors.append(f"Nguyên liệu '{m['material_name']}' thiếu nhà cung cấp")
            eligibility_snapshot = _json_obj(_record_get(m, "eligibility_snapshot"))
        else:
            try:
                eligibility = await assert_supplier_eligible(db, str(tenant_id), supplier_id, _record_get(m, "category"))
                eligibility_snapshot = {
                    "supplier_id": supplier_id,
                    "eligibility_id": eligibility.certificate_id,
                    "status": eligibility.status,
                    "valid_from": eligibility.valid_from.isoformat() if eligibility.valid_from else None,
                    "valid_until": eligibility.valid_until.isoformat() if eligibility.valid_until else None,
                    "source_of_truth": eligibility.source_of_truth,
                    "scope": eligibility.scope,
                    "checked_at": datetime.utcnow().isoformat() + "Z",
                }
            except HTTPException as exc:
                readiness_errors.append(f"Nguyên liệu '{m['material_name']}' không còn đủ điều kiện CB: {exc.detail}")
                eligibility_snapshot = _json_obj(_record_get(m, "eligibility_snapshot"))

        material_snapshots.append(
            {
                "material_name": m["material_name"],
                "sku": _record_get(m, "sku"),
                "category": _record_get(m, "category"),
                "halal_risk": _record_get(m, "halal_risk") or "unknown",
                "supplier_name": _record_get(m, "supplier_name"),
                "supplier_id": supplier_id,
                "quantity": float(m["quantity"]) if m["quantity"] is not None else None,
                "unit": _record_get(m, "unit"),
                "eligibility_snapshot": eligibility_snapshot,
            }
        )

    if readiness_errors:
        raise HTTPException(
            400,
            {"message": "Lô hàng chưa đủ điều kiện seal", "reasons": readiness_errors},
        )

    approver = user.get("email", "admin")
    approved_at = datetime.utcnow().isoformat()

    # Build sealed data snapshot. Keep legacy top-level keys for older verify/tests,
    # but also include normalized nested payload for public trace rendering.
    sealed = {
        "snapshot_version": 2,
        "hash_algorithm": "sha256",
        "batch_code": row["batch_code"],
        "product_name": row["product_name"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "approved_by": approver,
        "approved_at": approved_at,
        "compliance_score": row["compliance_score"],
        "company_name": _record_get(row, "company_name") or "N/A",
        "batch": {
            "id": bid,
            "batch_code": row["batch_code"],
            "product_name": row["product_name"],
            "status": row["status"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "created_at": row["created_at"].isoformat() if _record_get(row, "created_at") else None,
            "compliance_score": row["compliance_score"],
        },
        "company": {"name": _record_get(row, "company_name") or "N/A"},
        "process": {
            "id": str(row["process_template_id"]) if _record_get(row, "process_template_id") else None,
            "name": _record_get(row, "process_name"),
            "description": _record_get(row, "process_description"),
            "version": _record_get(row, "process_version"),
        },
        "steps": [
            {
                "step_name": s["step_name"],
                "performed_by": s["performed_by"],
                "started_at": s["started_at"].isoformat() if s["started_at"] else None,
                "completed_at": s["completed_at"].isoformat() if s["completed_at"] else None,
                "status": s["status"],
                "approved_by": s["approved_by"],
                "approved_at": s["approved_at"].isoformat() if s["approved_at"] else None,
                "notes": s["notes"],
                "checklist": _json_list(_record_get(s, "checklist")),
                "has_photo": bool(s["photo_path"]),
            }
            for s in steps
        ],
        "materials": material_snapshots,
        "certificates": [
            {
                "supplier_name": c["supplier_name"],
                "cert_type": c["cert_type"],
                "cert_number": c["cert_number"],
                "issuing_body": c["issuing_body"],
                "issued_date": c["issued_date"].isoformat() if c["issued_date"] else None,
                "expiry_date": c["expiry_date"].isoformat() if c["expiry_date"] else None,
            }
            for c in certs
        ],
    }

    integrity_hash = _integrity_hash(sealed)

    # Also hash each step individually
    for i, s in enumerate(steps):
        step_hash = _integrity_hash(sealed["steps"][i])
        await db.execute("UPDATE batch_steps SET step_hash=$1 WHERE id=$2", step_hash, s["id"])

    # Seal the batch — after this, data is immutable and public trace can be served.
    sealed_json = _canonical_json(sealed)
    await db.execute(
        """
        UPDATE production_batches
        SET approved_by=$1, approved_at=NOW(), integrity_hash=$2,
            sealed_data=$3::jsonb, public_trace_enabled=true
        WHERE id=$4
    """,
        approver,
        integrity_hash,
        sealed_json,
        bid,
    )

    log.info(f"[batches] Sealed {bid} hash={integrity_hash[:16]}...")
    return {
        "message": "Lô hàng đã được seal và xác nhận",
        "integrity_hash": integrity_hash,
        "unapproved_steps": 0,
        "sealed": True,
    }


@router.get("/batches/{bid}/verify")
async def verify_batch_integrity(bid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Verify batch data hasn't been tampered with after sealing."""
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    row = await db.fetchrow(
        "SELECT integrity_hash, sealed_data::text AS sealed_text FROM production_batches WHERE id=$1 AND tenant_id=$2",
        bid,
        tenant_id,
    )
    if not row:
        raise HTTPException(404)
    if not row["integrity_hash"]:
        return {"verified": False, "reason": "Lô hàng chưa được seal"}

    # Parse raw text then re-serialize identically to seal time
    sealed = _json.loads(row["sealed_text"])
    computed_hash = _integrity_hash(sealed)
    is_valid = computed_hash == row["integrity_hash"]

    return {
        "verified": is_valid,
        "stored_hash": row["integrity_hash"],
        "computed_hash": computed_hash,
        "sealed_at": sealed.get("approved_at") if isinstance(sealed, dict) else None,
        "message": "Dữ liệu toàn vẹn — chưa bị thay đổi" if is_valid else "CẢNH BÁO: Dữ liệu đã bị thay đổi!",
    }


@router.post("/batches/{bid}/export-pdf")
async def export_batch_pdf(bid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Export batch report as PDF with QR code."""
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    row = await db.fetchrow(
        """
        SELECT b.*, p.name AS process_name
        FROM production_batches b
        LEFT JOIN process_templates p ON p.id = b.process_template_id
        WHERE b.id=$1 AND b.tenant_id=$2
    """,
        bid,
        tenant_id,
    )
    if not row:
        raise HTTPException(404)

    steps = await db.fetch("SELECT * FROM batch_steps WHERE batch_id=$1 ORDER BY created_at", bid)
    mats = await db.fetch(
        """
        SELECT bm.*, m.name AS material_name, m.sku, s.name AS supplier_name
        FROM batch_materials bm
        JOIN materials m ON m.id = bm.material_id
        LEFT JOIN suppliers s ON s.id = m.supplier_id
        WHERE bm.batch_id=$1
    """,
        bid,
    )

    # Get company name
    company = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", tenant_id)
    company_name = company["company_name"] if company else "N/A"

    # Generate QR
    qr_url = _trace_url(str(row["public_trace_id"]))
    qr_img_bytes = None
    try:
        import qrcode

        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#087653", back_color="white")
        import io as _io

        qr_buf = _io.BytesIO()
        img.save(qr_buf, format="PNG")
        qr_img_bytes = qr_buf.getvalue()
    except ImportError:
        pass

    # Build PDF using reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        raise HTTPException(500, "reportlab not installed — fallback to DOCX")

    # Register Unicode font for Vietnamese
    _font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    _font_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    pdfmetrics.registerFont(TTFont("VNFont", _font_path))
    pdfmetrics.registerFont(TTFont("VNFontBold", _font_bold_path))

    import io as _io

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="VN", fontName="VNFont", fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="VNBold", fontName="VNFontBold", fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="Title2", fontName="VNFontBold", fontSize=16, leading=20, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Sub", fontName="VNFont", fontSize=9, leading=12, textColor=colors.grey))

    elements = []

    # QR + Header side by side
    if qr_img_bytes:
        qr_image = Image(_io.BytesIO(qr_img_bytes), width=25 * mm, height=25 * mm)
        header_data = [[qr_image, Paragraph(f"<b>BÁO CÁO LÔ HÀNG</b><br/>{row['batch_code']}", styles["Title2"])]]
        header_table = Table(header_data, colWidths=[30 * mm, 140 * mm])
        header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elements.append(header_table)
    else:
        elements.append(Paragraph(f"BÁO CÁO LÔ HÀNG: {row['batch_code']}", styles["Title2"]))

    elements.append(Spacer(1, 5 * mm))

    # Info table
    status_map = {"draft": "Nháp", "in_progress": "Đang sản xuất", "completed": "Hoàn thành", "rejected": "Từ chối"}
    info_data = [
        ["Mã lô", row["batch_code"]],
        ["Sản phẩm", row["product_name"]],
        ["Công ty", company_name],
        ["Quy trình", _record_get(row, "process_name") or "N/A"],
        ["Trạng thái", status_map.get(row["status"], row["status"])],
        ["Bắt đầu", str(row["started_at"] or "Chưa bắt đầu")],
        ["Hoàn thành", str(row["completed_at"] or "Chưa hoàn thành")],
        ["Điểm tuân thủ", f"{row['compliance_score']}%" if row["compliance_score"] is not None else "N/A"],
    ]
    if _record_get(row, "approved_by"):
        info_data.append(["Xác nhận bởi", row["approved_by"]])
        info_data.append(["Ngày xác nhận", str(row.get("approved_at", ""))])
    if _record_get(row, "integrity_hash"):
        info_data.append(["Hash toàn vẹn", row["integrity_hash"][:32] + "..."])

    info_table = Table(info_data, colWidths=[45 * mm, 125 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "VNFontBold"),
                ("FONTNAME", (1, 0), (1, -1), "VNFont"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1A2332")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 8 * mm))

    # Materials
    if mats:
        elements.append(Paragraph("<b>NGUYÊN LIỆU SỬ DỤNG</b>", styles["VNBold"]))
        elements.append(Spacer(1, 3 * mm))
        mat_data = [["Nguyên liệu", "SKU", "NCC", "Số lượng", "Đơn vị"]]
        for m in mats:
            mat_data.append(
                [
                    m["material_name"],
                    _record_get(m, "sku") or "",
                    m["supplier_name"] or "",
                    str(m["quantity"] or ""),
                    _record_get(m, "unit") or "",
                ]
            )
        mat_table = Table(mat_data, colWidths=[50 * mm, 25 * mm, 40 * mm, 25 * mm, 25 * mm])
        mat_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "VNFontBold"),
                    ("FONTNAME", (0, 1), (-1, -1), "VNFont"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F7F4")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(mat_table)
        elements.append(Spacer(1, 8 * mm))

    # Steps
    if steps:
        elements.append(Paragraph("<b>CÁC BƯỚC THỰC HIỆN</b>", styles["VNBold"]))
        elements.append(Spacer(1, 3 * mm))
        step_data = [["#", "Tên bước", "Người TH", "Bắt đầu", "Kết thúc", "Trạng thái", "Xác nhận"]]
        for i, s in enumerate(steps, 1):
            step_data.append(
                [
                    str(i),
                    s["step_name"],
                    _record_get(s, "performed_by") or "",
                    s["started_at"].strftime("%d/%m %H:%M") if _record_get(s, "started_at") else "",
                    s["completed_at"].strftime("%d/%m %H:%M") if _record_get(s, "completed_at") else "",
                    "Xong" if s["status"] == "completed" else "Chưa",
                    _record_get(s, "approved_by") or "",
                ]
            )
        step_table = Table(step_data, colWidths=[8 * mm, 40 * mm, 30 * mm, 22 * mm, 22 * mm, 18 * mm, 30 * mm])
        step_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "VNFontBold"),
                    ("FONTNAME", (0, 1), (-1, -1), "VNFont"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F7F4")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        elements.append(step_table)
        elements.append(Spacer(1, 8 * mm))

    # QR section
    elements.append(Paragraph("<b>TRUY XUẤT NGUỒN GỐC</b>", styles["VNBold"]))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(f"Quét mã QR hoặc truy cập: {qr_url}", styles["Sub"]))
    if qr_img_bytes:
        elements.append(Spacer(1, 3 * mm))
        elements.append(Image(_io.BytesIO(qr_img_bytes), width=35 * mm, height=35 * mm))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(f"Báo cáo được tạo tự động bởi AMINRA · {company_name}", styles["Sub"]))

    doc.build(elements)
    buf.seek(0)

    import urllib.parse

    safe_code = urllib.parse.quote(row["batch_code"])
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_code}_report.pdf"},
    )


@router.post("/batches/{bid}/steps/{step_id}/photo")
async def upload_step_photo(
    bid: str, step_id: str, file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)
):
    _validate_uuid(bid)
    _validate_uuid(step_id)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_upload")

    # Tenant boundary: the step must belong to a batch owned by the caller's tenant.
    # Checking only (step_id, batch_id) lets a tenant overwrite another tenant's
    # evidence path when IDs are leaked from trace/PDF/QR workflows.
    step = await db.fetchrow(
        """
        SELECT s.id, b.integrity_hash
        FROM batch_steps s
        JOIN production_batches b ON b.id = s.batch_id
        WHERE s.id=$1 AND s.batch_id=$2 AND b.tenant_id=$3
        """,
        step_id,
        bid,
        tenant_id,
    )
    if not step:
        raise HTTPException(404, "Bước sản xuất không tồn tại")
    if step.get("integrity_hash"):
        raise HTTPException(403, "Lô hàng đã được seal — không thể thay đổi")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Ảnh quá lớn (tối đa 5MB)")

    save_dir = Path("docs") / tenant_id / "batch_photos" / bid
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (file.filename or "photo.jpg")).strip()
    fname = f"{step_id}_{safe_name or 'photo.jpg'}"
    save_path = save_dir / fname
    save_path.write_bytes(content)

    result = await db.execute(
        "UPDATE batch_steps SET photo_path=$1 WHERE id=$2 AND batch_id=$3",
        str(save_path),
        step_id,
        bid,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Bước sản xuất không tồn tại")
    return {"message": "Đã upload ảnh"}


@router.get("/batches/{bid}/steps/{step_id}/photo/view")
async def view_step_photo(bid: str, step_id: str, request: Request, token: Optional[str] = Query(None)):
    """View step photo. Supports ?token= for window.open."""
    from auth.jwt_utils import decode_token

    _validate_uuid(bid)
    _validate_uuid(step_id)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user = decode_token(auth[7:])
    elif token:
        user = decode_token(token)
    else:
        raise HTTPException(401)
    tenant_id = _require_business(user)

    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            """
            SELECT s.photo_path
            FROM batch_steps s
            JOIN production_batches b ON b.id = s.batch_id
            WHERE s.id=$1 AND s.batch_id=$2 AND b.tenant_id=$3
            """,
            step_id,
            bid,
            tenant_id,
        )
    if not row or not row["photo_path"]:
        raise HTTPException(404, "Ảnh không tồn tại")

    fpath = Path(row["photo_path"])
    if not fpath.exists():
        raise HTTPException(404, "File không tồn tại")

    import magic as _magic

    detected = _magic.from_buffer(fpath.read_bytes()[:2048], mime=True)
    from fastapi.responses import FileResponse

    return FileResponse(path=str(fpath), media_type=detected if detected.startswith("image/") else "image/jpeg")


# ── QR Code ───────────────────────────────────────────────────────────────────


@router.get("/batches/{bid}/qr")
async def generate_qr(bid: str, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    """Generate QR code PNG for a batch."""
    _validate_uuid(bid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT batch_code, public_trace_id FROM production_batches WHERE id=$1 AND tenant_id=$2", bid, tenant_id)
    if not row:
        raise HTTPException(404)

    url = _trace_url(str(row["public_trace_id"]), request)

    try:
        import qrcode
    except ImportError:
        return {"url": url, "batch_code": row["batch_code"], "image": None}
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#087653", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # Save URL to DB
    await db.execute("UPDATE production_batches SET qr_code_url=$1 WHERE id=$2", url, bid)

    return Response(
        content=buf.read(),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="QR_{row["batch_code"]}.png"'},
    )
