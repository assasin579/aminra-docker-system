"""Supplier CRUD + certificate management."""

import logging
import json as _json
import magic
from uuid import UUID as _UUID, uuid4
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse

from auth.db import get_db
from auth.jwt_utils import get_current_user, decode_token
from auth.permissions import check_permission_db
from .models import SupplierCreate, SupplierUpdate, SupplierOut, CertificateOut

log = logging.getLogger("aminra.supply_chain.suppliers")
router = APIRouter()

CERT_DIR = Path("docs/supplier_certs")
CERT_DIR.mkdir(parents=True, exist_ok=True)


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


# ── CRUD Suppliers ───────────────────────────────────────────────────────────

@router.get("/suppliers")
async def list_suppliers(
    status: Optional[str] = Query(None),
    user=Depends(get_current_user), db=Depends(get_db),
):
    tenant_id = _require_business(user)
    cond = "WHERE s.tenant_id = $1"
    params = [tenant_id]
    if status:
        cond += " AND s.status = $2"
        params.append(status)

    rows = await db.fetch(f"""
        SELECT s.*,
            (SELECT COUNT(*) FROM materials m WHERE m.supplier_id = s.id) AS material_count,
            (SELECT COUNT(*) FROM supplier_certificates c WHERE c.supplier_id = s.id) AS cert_count
        FROM suppliers s {cond} ORDER BY s.created_at DESC
    """, *params)

    return {"suppliers": [
        SupplierOut(
            id=str(r["id"]), name=r["name"], address=r["address"], phone=r["phone"],
            email=r["email"], contact_person=r["contact_person"],
            supplier_type=r["supplier_type"], tax_code=r.get("tax_code"), status=r["status"], notes=r["notes"],
            material_count=r["material_count"], cert_count=r["cert_count"],
            created_at=r["created_at"],
        ) for r in rows
    ]}


@router.post("/suppliers")
async def create_supplier(
    req: SupplierCreate,
    user=Depends(get_current_user), db=Depends(get_db),
):
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    row = await db.fetchrow("""
        INSERT INTO suppliers (tenant_id, name, address, phone, email, contact_person, supplier_type, tax_code, notes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id
    """, tenant_id, req.name, req.address, req.phone, req.email,
        req.contact_person, req.supplier_type, req.tax_code, req.notes)
    log.info(f"[suppliers] Created {row['id']} for tenant {tenant_id}")
    return {"id": str(row["id"]), "message": "Đã tạo nhà cung cấp"}


@router.get("/suppliers/{sid}")
async def get_supplier(sid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT * FROM suppliers WHERE id=$1 AND tenant_id=$2", sid, tenant_id)
    if not row:
        raise HTTPException(404)
    return dict(row)


@router.put("/suppliers/{sid}")
async def update_supplier(sid: str, req: SupplierUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    updates, params, idx = [], [sid, tenant_id], 3
    for field in ["name", "address", "phone", "email", "contact_person", "supplier_type", "tax_code", "status", "notes"]:
        val = getattr(req, field, None)
        if val is not None:
            updates.append(f"{field} = ${idx}")
            params.append(val)
            idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    result = await db.execute(
        f"UPDATE suppliers SET {', '.join(updates)} WHERE id=$1 AND tenant_id=$2", *params)
    if result == "UPDATE 0":
        raise HTTPException(404)
    return {"message": "Đã cập nhật"}


@router.delete("/suppliers/{sid}")
async def delete_supplier(sid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_delete")
    result = await db.execute("DELETE FROM suppliers WHERE id=$1 AND tenant_id=$2", sid, tenant_id)
    if result == "DELETE 0":
        raise HTTPException(404)
    return {"message": "Đã xoá"}


# ── Supplier Certificates ────────────────────────────────────────────────────

@router.get("/suppliers/{sid}/certificates")
async def list_certificates(sid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    rows = await db.fetch(
        "SELECT * FROM supplier_certificates WHERE supplier_id=$1 AND tenant_id=$2 ORDER BY created_at DESC",
        sid, tenant_id)
    return {"certificates": [
        CertificateOut(
            id=str(r["id"]), cert_type=r["cert_type"], cert_number=r["cert_number"],
            issuing_body=r["issuing_body"], issued_date=r["issued_date"],
            expiry_date=r["expiry_date"], original_filename=r["original_filename"],
            file_size=r["file_size"], created_at=r["created_at"],
        ) for r in rows
    ]}


@router.post("/suppliers/{sid}/certificates")
async def upload_certificate(
    sid: str,
    file: UploadFile = File(...),
    cert_type: str = Form("halal_cert"),
    cert_number: str = Form(""),
    issuing_body: str = Form(""),
    issued_date: str = Form(""),
    expiry_date: str = Form(""),
    user=Depends(get_current_user), db=Depends(get_db),
):
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_upload")

    # Verify supplier belongs to tenant
    s = await db.fetchrow("SELECT id FROM suppliers WHERE id=$1 AND tenant_id=$2", sid, tenant_id)
    if not s:
        raise HTTPException(404)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File quá lớn (tối đa 10MB)")

    detected = magic.from_buffer(content, mime=True)
    allowed = {"application/pdf", "image/jpeg", "image/png",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               "application/octet-stream", "application/zip"}
    if detected not in allowed:
        raise HTTPException(400, f"Loại file không hợp lệ: {detected}")

    cert_id = str(uuid4())
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (file.filename or "cert")).strip()
    save_dir = CERT_DIR / tenant_id / sid
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{cert_id}_{safe_name}"
    save_path.write_bytes(content)

    _issued = None
    _expiry = None
    try:
        if issued_date:
            from datetime import date as _date
            _issued = _date.fromisoformat(issued_date)
        if expiry_date:
            from datetime import date as _date
            _expiry = _date.fromisoformat(expiry_date)
    except ValueError:
        pass

    row = await db.fetchrow("""
        INSERT INTO supplier_certificates
            (supplier_id, tenant_id, cert_type, cert_number, issuing_body,
             issued_date, expiry_date, file_path, original_filename, file_size)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id
    """, sid, tenant_id, cert_type, cert_number or None, issuing_body or None,
        _issued, _expiry, str(save_path), file.filename, len(content))

    return {"id": str(row["id"]), "filename": file.filename}


@router.get("/suppliers/{sid}/certificates/{cid}/view")
async def view_certificate(
    sid: str, cid: str, request: Request, token: Optional[str] = Query(None),
):
    """View certificate as PDF. Supports ?token= for window.open."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user = decode_token(auth[7:])
    elif token:
        user = decode_token(token)
    else:
        raise HTTPException(401)

    from auth.db import get_pool
    pool = get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT file_path, original_filename FROM supplier_certificates WHERE id=$1 AND supplier_id=$2",
            cid, sid)
    if not row or not row["file_path"]:
        raise HTTPException(404)

    fpath = Path(row["file_path"])
    if not fpath.exists():
        raise HTTPException(404, "File không tồn tại")

    detected = magic.from_buffer(fpath.read_bytes()[:2048], mime=True)
    if detected == "application/pdf" or fpath.suffix.lower() == ".pdf":
        return FileResponse(path=str(fpath), media_type="application/pdf")
    if detected.startswith("image/"):
        return FileResponse(path=str(fpath), media_type=detected)

    # Convert to PDF
    import subprocess, os
    from starlette.concurrency import run_in_threadpool
    cache_dir = Path("data/preview_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_pdf = cache_dir / f"cert_{cid}.pdf"
    if cache_pdf.exists() and cache_pdf.stat().st_size > 0:
        return FileResponse(path=str(cache_pdf), media_type="application/pdf")

    pid_profile = f"/tmp/lo_profile_{os.getpid()}"
    os.makedirs(pid_profile, exist_ok=True)

    def _convert():
        subprocess.run(
            ["/usr/bin/libreoffice", "--headless", "--norestore", "--nolockcheck",
             f"-env:UserInstallation=file://{pid_profile}",
             "--convert-to", "pdf", "--outdir", str(cache_dir.resolve()), str(fpath.resolve())],
            capture_output=True, timeout=60, cwd="/tmp",
            env={"HOME": pid_profile, "PATH": "/usr/bin:/usr/local/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        lo_output = cache_dir / (fpath.stem + ".pdf")
        if lo_output.exists():
            lo_output.rename(cache_pdf)

    await run_in_threadpool(_convert)
    if not cache_pdf.exists():
        raise HTTPException(500, "Chuyển đổi PDF thất bại")
    return FileResponse(path=str(cache_pdf), media_type="application/pdf")


@router.delete("/suppliers/{sid}/certificates/{cid}")
async def delete_certificate(sid: str, cid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(sid)
    _validate_uuid(cid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_delete")
    row = await db.fetchrow(
        "SELECT file_path FROM supplier_certificates WHERE id=$1 AND supplier_id=$2 AND tenant_id=$3",
        cid, sid, tenant_id)
    if not row:
        raise HTTPException(404)
    if row["file_path"]:
        p = Path(row["file_path"])
        p.unlink(missing_ok=True)
    await db.execute("DELETE FROM supplier_certificates WHERE id=$1", cid)
    return {"message": "Đã xoá"}


# ── Invite & Supplier Portal (public) ─────────────────────────────────────────

@router.post("/suppliers/{sid}/invite")
async def generate_invite(sid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Generate invite link for supplier to upload their own certificates."""
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    s = await db.fetchrow("SELECT id FROM suppliers WHERE id=$1 AND tenant_id=$2", sid, tenant_id)
    if not s:
        raise HTTPException(404)

    from datetime import timedelta, datetime, timezone
    token = str(uuid4()).replace("-", "")
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    await db.execute(
        "UPDATE suppliers SET invite_token=$1, invite_expires_at=$2 WHERE id=$3",
        token, expires, sid)

    log.info(f"[suppliers] Invite generated for {sid}")
    return {
        "invite_token": token,
        "expires_at": expires.isoformat(),
        "portal_url": f"/supplier-portal/{token}",
        "message": "Link mời hồ sơ đã tạo (hết hạn sau 30 ngày)",
    }


@router.get("/supplier-portal/{token}")
async def get_portal_info(token: str, db=Depends(get_db)):
    """Public: NCC xem yêu cầu hồ sơ (no auth needed)."""
    from datetime import datetime, timezone
    row = await db.fetchrow("""
        SELECT s.id, s.name, s.invite_expires_at, s.tenant_id,
               u.company_name AS business_name
        FROM suppliers s
        JOIN users u ON u.id = s.tenant_id AND u.is_owner = true
        WHERE s.invite_token = $1
    """, token)

    if not row:
        raise HTTPException(404, "Link không hợp lệ hoặc đã hết hạn")
    if row["invite_expires_at"] and row["invite_expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(410, "Link đã hết hạn")

    # Get existing certs uploaded by supplier
    certs = await db.fetch(
        "SELECT id, cert_type, original_filename, file_size, created_at FROM supplier_certificates WHERE supplier_id=$1 ORDER BY created_at DESC",
        row["id"])

    return {
        "supplier_name": row["name"],
        "business_name": row["business_name"],
        "required_documents": [
            {"type": "halal_cert", "label": "Chứng nhận Halal", "required": True},
            {"type": "business_license", "label": "Giấy phép kinh doanh", "required": False},
            {"type": "food_safety", "label": "Chứng nhận ATTP", "required": False},
            {"type": "lab_result", "label": "Kết quả kiểm nghiệm", "required": False},
            {"type": "iso_haccp", "label": "ISO 22000 / HACCP", "required": False},
            {"type": "contract", "label": "Hợp đồng cung cấp", "required": False},
        ],
        "uploaded_certificates": [
            {"id": str(c["id"]), "cert_type": c["cert_type"],
             "filename": c["original_filename"], "size": c["file_size"],
             "uploaded_at": c["created_at"].isoformat()}
            for c in certs
        ],
    }


@router.post("/supplier-portal/{token}/upload")
async def portal_upload(token: str, file: UploadFile = File(...), cert_type: str = Form("halal_cert"), db=Depends(get_db)):
    """Public: NCC upload chứng chỉ (no auth, uses invite token)."""
    from datetime import datetime, timezone
    row = await db.fetchrow(
        "SELECT id, tenant_id, invite_expires_at FROM suppliers WHERE invite_token=$1", token)

    if not row:
        raise HTTPException(404, "Link không hợp lệ")
    if row["invite_expires_at"] and row["invite_expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(410, "Link đã hết hạn")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File quá lớn (tối đa 10MB)")

    detected = magic.from_buffer(content, mime=True)
    allowed = {"application/pdf", "image/jpeg", "image/png",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               "application/octet-stream", "application/zip"}
    if detected not in allowed:
        raise HTTPException(400, f"Loại file không hợp lệ: {detected}")

    sid = str(row["id"])
    tenant_id = str(row["tenant_id"])
    cert_id = str(uuid4())
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (file.filename or "cert")).strip()
    save_dir = CERT_DIR / tenant_id / sid
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{cert_id}_{safe_name}"
    save_path.write_bytes(content)

    await db.execute("""
        INSERT INTO supplier_certificates
            (supplier_id, tenant_id, cert_type, file_path, original_filename, file_size, uploaded_by)
        VALUES ($1,$2,$3,$4,$5,$6,'supplier')
    """, sid, tenant_id, cert_type, str(save_path), file.filename, len(content))

    log.info(f"[supplier-portal] NCC {sid} uploaded {cert_type}")
    return {"message": "Đã gửi hồ sơ thành công", "filename": file.filename}


@router.get("/suppliers/{sid}/verification-status")
async def verification_status(sid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Check if supplier meets verification requirements."""
    _validate_uuid(sid)
    tenant_id = _require_business(user)
    s = await db.fetchrow("SELECT id, status, invite_token FROM suppliers WHERE id=$1 AND tenant_id=$2", sid, tenant_id)
    if not s:
        raise HTTPException(404)

    certs = await db.fetch(
        "SELECT cert_type, uploaded_by FROM supplier_certificates WHERE supplier_id=$1", sid)

    has_halal = any(c["cert_type"] == "halal_cert" for c in certs)
    supplier_uploaded = any(c["uploaded_by"] == "supplier" for c in certs)
    total_certs = len(certs)

    can_verify = has_halal  # Minimum: must have Halal cert

    return {
        "status": s["status"],
        "has_invite": bool(s["invite_token"]),
        "total_certs": total_certs,
        "has_halal_cert": has_halal,
        "supplier_uploaded": supplier_uploaded,
        "can_verify": can_verify,
        "checklist": [
            {"item": "Chứng nhận Halal", "done": has_halal, "required": True},
            {"item": "NCC tự gửi hồ sơ", "done": supplier_uploaded, "required": False},
            {"item": "Có ≥ 2 chứng chỉ", "done": total_certs >= 2, "required": False},
        ],
    }


@router.post("/suppliers/{sid}/verify")
async def verify_supplier(sid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Mark supplier as verified (requires Halal cert)."""
    _validate_uuid(sid)
    tenant_id = _require_business(user)

    # Check requirements
    has_halal = await db.fetchval(
        "SELECT COUNT(*) FROM supplier_certificates WHERE supplier_id=$1 AND cert_type='halal_cert'", sid)
    if not has_halal:
        raise HTTPException(400, "Không thể xác minh: chưa có chứng nhận Halal")

    result = await db.execute(
        "UPDATE suppliers SET status='verified' WHERE id=$1 AND tenant_id=$2 AND status != 'verified'",
        sid, tenant_id)
    if result == "UPDATE 0":
        raise HTTPException(400, "NCC đã được xác minh hoặc không tồn tại")

    log.info(f"[suppliers] Verified {sid}")
    return {"message": "Đã xác minh nhà cung cấp"}
