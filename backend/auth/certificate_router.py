"""Halal Certificate issuance — generate cert PDF after submission approval."""

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional
from uuid import UUID as _UUID

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from asyncpg import Connection

from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.notification_router import notify
from services.audit_log import log_audit
from services.certificate_pdf import CertificateData, generate_pdf

log = logging.getLogger("aminra.certificates")

CERT_PDF_DIR = Path(os.getenv("CERT_PDF_DIR", "docs/certificates"))
router = APIRouter()


def _validate_uuid(v: str) -> str:
    try:
        _UUID(v)
    except ValueError:
        raise HTTPException(400, "Invalid ID")
    return v


class IssueCertRequest(BaseModel):
    expiry_months: int = 12
    notes: str = ""


@router.post("/received/{submission_id}/issue-certificate")
async def issue_certificate_legacy(
    submission_id: str,
    req: IssueCertRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Legacy: redirect to company-level cert issuance."""
    _validate_uuid(submission_id)
    sub = await db.fetchrow("SELECT business_tenant FROM submissions WHERE id=$1", submission_id)
    if not sub:
        raise HTTPException(404)
    # Delegate to company-level
    return await issue_certificate_for_company(str(sub["business_tenant"]), req, user, db)


@router.post("/issue-certificate/{business_tenant_id}")
async def issue_certificate_for_company(
    business_tenant_id: str,
    req: IssueCertRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Provider owner issues Halal certificate for a company — ALL submissions must be approved."""
    _validate_uuid(business_tenant_id)
    if user["role"] != "provider" or not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức mới được cấp chứng nhận")

    provider_id = user.get("tenant_id") or user["sub"]

    # All currently-active dossiers must be approved before cert can be issued.
    # Terminal-state 'rejected' submissions are historical and don't block future certs.
    active_subs = await db.fetch(
        "SELECT id, status FROM submissions WHERE business_tenant=$1 AND provider_id=$2 AND status <> 'rejected'",
        business_tenant_id,
        provider_id,
    )
    if not active_subs:
        raise HTTPException(404, "Không tìm thấy hồ sơ đang hoạt động từ doanh nghiệp này")

    not_approved = [s for s in active_subs if s["status"] != "approved"]
    if not_approved:
        raise HTTPException(
            400,
            f"Còn {len(not_approved)} hồ sơ chưa được duyệt. Phải duyệt tất cả hồ sơ đang hoạt động trước khi cấp chứng nhận.",
        )

    # Check if active cert already exists for this company
    existing = await db.fetchrow(
        "SELECT id, cert_number FROM halal_certificates WHERE business_tenant=$1 AND issued_by=$2 AND status='active'",
        business_tenant_id,
        provider_id,
    )
    if existing:
        raise HTTPException(400, f"Chứng nhận đã được cấp: {existing['cert_number']}")

    # W4-M3 fix — preserve day-of-month using dateutil; old code dropped 31→28.
    from dateutil.relativedelta import relativedelta

    issue_date = date.today()
    expiry_date = issue_date + relativedelta(months=req.expiry_months)

    # Get names (used in PDF)
    provider = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", user["sub"])
    provider_name = provider["company_name"] if provider else "N/A"
    biz_user = await db.fetchrow(
        "SELECT company_name FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", business_tenant_id
    )
    business_name = biz_user["company_name"] if biz_user else "N/A"

    # C10 + C11 fix — INSERT first with retry-on-collision, write PDF after.
    # Old order (PDF→INSERT) leaked orphan PDFs when INSERT failed (e.g., race
    # producing same cert_number).
    app_base = os.getenv("APP_BASE_URL", "http://localhost:3100").rstrip("/")
    year = date.today().year
    cert_number = ""
    cert_id = None
    last_err = None
    for attempt in range(5):
        count = await db.fetchval(
            "SELECT COUNT(*) FROM halal_certificates WHERE cert_number LIKE $1",
            f"HALAL-{year}-%",
        )
        candidate = f"HALAL-{year}-{(count or 0) + 1 + attempt:04d}"
        try:
            row = await db.fetchrow(
                """
                INSERT INTO halal_certificates (cert_number, issued_by, business_tenant, company_name,
                                                issue_date, expiry_date, pdf_path, notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
            """,
                candidate,
                user["sub"],
                business_tenant_id,
                business_name,
                issue_date,
                expiry_date,
                "",
                req.notes,
            )
            cert_number = candidate
            cert_id = row["id"]
            break
        except Exception as e:
            last_err = e
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                continue
            raise
    if not cert_number:
        log.exception(f"[cert] cert_number generation exhausted retries: {last_err}")
        raise HTTPException(500, "Không tạo được số chứng nhận sau nhiều lần thử")

    # Now generate PDF using the locked-in cert_number, write to disk.
    cert_data = CertificateData(
        cert_number=cert_number,
        business_name=business_name,
        provider_name=provider_name,
        issue_date=issue_date,
        expiry_date=expiry_date,
        notes=req.notes or "",
        verify_url=f"{app_base}/verify/{cert_number}",
    )
    try:
        pdf_bytes = generate_pdf(cert_data)
        CERT_PDF_DIR.mkdir(parents=True, exist_ok=True)
        pdf_file = CERT_PDF_DIR / f"{cert_number}.pdf"
        pdf_file.write_bytes(pdf_bytes)
        pdf_path = str(pdf_file)
        await db.execute(
            "UPDATE halal_certificates SET pdf_path = $1 WHERE id = $2",
            pdf_path,
            cert_id,
        )
    except ValueError as e:
        # PDF data invalid — roll back the cert row to avoid orphans.
        await db.execute("DELETE FROM halal_certificates WHERE id = $1", cert_id)
        raise HTTPException(400, f"Dữ liệu chứng nhận không hợp lệ: {e}")
    except Exception as e:
        await db.execute("DELETE FROM halal_certificates WHERE id = $1", cert_id)
        log.exception("[cert] PDF generation failed; cert row rolled back")
        raise HTTPException(500, f"Không thể tạo PDF chứng nhận: {e}")
    row = {"id": cert_id}

    log.info(f"[cert] Issued {cert_number} for business {business_tenant_id}")

    await log_audit(
        db,
        user=user,
        action="certificate.issue",
        entity_type="certificate",
        entity_id=str(row["id"]),
        metadata={
            "cert_number": cert_number,
            "business_tenant": business_tenant_id,
            "expiry_date": expiry_date.isoformat(),
        },
    )

    # Notify business owner
    biz_owner = await db.fetchrow(
        "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", business_tenant_id
    )
    if biz_owner:
        await notify(
            db,
            str(biz_owner["id"]),
            "certificate",
            f"Chứng nhận Halal đã được cấp: {cert_number}",
            f"Có hiệu lực đến {expiry_date.strftime('%d/%m/%Y')}",
            "/dashboard/business",
        )

    return {
        "id": str(row["id"]),
        "cert_number": cert_number,
        "pdf_url": f"/api/api/submissions/certificates/{row['id']}/pdf",
        "issue_date": issue_date.isoformat(),
        "expiry_date": expiry_date.isoformat(),
        "message": f"Đã cấp chứng nhận {cert_number}",
    }


@router.get("/certificates")
async def list_certificates(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """List certificates — provider sees issued, business sees received."""
    if user["role"] == "provider":
        rows = await db.fetch(
            "SELECT * FROM halal_certificates WHERE issued_by=$1 ORDER BY created_at DESC", user["sub"]
        )
    elif user["role"] == "business":
        rows = await db.fetch(
            "SELECT * FROM halal_certificates WHERE business_tenant=$1 ORDER BY created_at DESC", user.get("tenant_id")
        )
    else:
        return {"certificates": []}

    return {
        "certificates": [
            {
                "id": str(r["id"]),
                "cert_number": r["cert_number"],
                "company_name": r["company_name"],
                "issue_date": r["issue_date"].isoformat(),
                "expiry_date": r["expiry_date"].isoformat(),
                "status": r["status"],
                "notes": r["notes"],
                "has_pdf": bool(r["pdf_path"]),
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/certificates/registry")
async def cert_registry(
    status: Optional[str] = Query(None),
    expiring_days: int = Query(0),
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Provider owner: full cert registry with filters and stats."""
    if user["role"] != "provider" or not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")
    provider_id = user.get("tenant_id") or user["sub"]

    # Stats
    stats = await db.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='active') AS active,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date < NOW() + INTERVAL '90 days') AS expiring_soon,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date < NOW()) AS expired,
            COUNT(*) FILTER (WHERE status='suspended') AS suspended,
            COUNT(*) FILTER (WHERE status='revoked') AS revoked
        FROM halal_certificates WHERE issued_by=$1
    """,
        provider_id,
    )

    # Filtered list
    where = "c.issued_by=$1"
    params = [provider_id]
    idx = 2
    if status:
        if status == "expiring":
            where += " AND c.status='active' AND c.expiry_date < NOW() + INTERVAL '90 days'"
        elif status == "expired":
            where += " AND c.status='active' AND c.expiry_date < NOW()"
        else:
            where += f" AND c.status=${idx}"
            params.append(status)
            idx += 1
    if expiring_days > 0:
        where += f" AND c.status='active' AND c.expiry_date < NOW() + INTERVAL '{int(expiring_days)} days'"

    rows = await db.fetch(
        f"""
        SELECT c.*, u.company_name AS provider_name
        FROM halal_certificates c
        LEFT JOIN users u ON u.id=c.issued_by
        WHERE {where}
        ORDER BY c.expiry_date ASC
    """,
        *params,
    )

    return {
        "stats": {
            "total": stats["total"],
            "active": stats["active"],
            "expiring_soon": stats["expiring_soon"],
            "expired": stats["expired"],
            "suspended": stats["suspended"],
            "revoked": stats["revoked"],
        },
        "certificates": [
            {
                "id": str(r["id"]),
                "cert_number": r["cert_number"],
                "company_name": r["company_name"],
                "issue_date": r["issue_date"].isoformat(),
                "expiry_date": r["expiry_date"].isoformat(),
                "status": r["status"],
                "notes": r["notes"],
                "has_pdf": bool(r["pdf_path"]),
                "days_remaining": (r["expiry_date"] - date.today()).days,
                "created_at": r["created_at"].isoformat(),
                # Revocation details (Gap 3) — surface to UI for trust
                "revocation_reason": r.get("revocation_reason"),
                "revoked_at": r["revoked_at"].isoformat() if r.get("revoked_at") else None,
                "revoked_by": str(r["revoked_by"]) if r.get("revoked_by") else None,
            }
            for r in rows
        ],
    }


@router.get("/certificates/public/{cert_number}")
async def public_verify_cert(cert_number: str, db: Connection = Depends(get_db)):
    """Public endpoint — NO AUTH. Verify a certificate by its number.

    Returns standard cert info plus blockchain anchor proof if available, so
    importers can independently verify on Polygon without trusting AMINRA.
    """
    import json as _json

    row = await db.fetchrow(
        """
        SELECT c.id, c.cert_number, c.company_name, c.issue_date, c.expiry_date, c.status,
               c.revocation_reason, c.revoked_at, c.revoked_by,
               u.company_name AS provider_name
        FROM halal_certificates c
        LEFT JOIN users u ON u.id=c.issued_by
        WHERE c.cert_number=$1
    """,
        cert_number.strip().upper(),
    )
    if not row:
        raise HTTPException(404, "Chứng nhận không tồn tại")

    is_expired = row["expiry_date"] < date.today() if row["expiry_date"] else False
    effective_status = "expired" if is_expired and row["status"] == "active" else row["status"]

    response = {
        "cert_number": row["cert_number"],
        "company_name": row["company_name"],
        "provider_name": row["provider_name"],
        "issue_date": row["issue_date"].isoformat(),
        "expiry_date": row["expiry_date"].isoformat(),
        "status": effective_status,
        "valid": effective_status == "active" and not is_expired,
        # Revocation details (Gap 3) — public visibility for importer trust
        "revocation": (
            {
                "reason": row["revocation_reason"],
                "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
            }
            if row.get("revoked_at")
            else None
        ),
    }

    # Blockchain anchor info — let the public verify independently on chain
    proof_row = await db.fetchrow(
        """
        SELECT p.leaf_hash, p.leaf_index, p.proof_path,
               a.id AS anchor_id, a.chain, a.merkle_root, a.tx_hash,
               a.block_number, a.confirmed_at, a.status AS anchor_status
        FROM cert_anchor_proofs p
        JOIN blockchain_anchors a ON a.id = p.anchor_id
        WHERE p.cert_id = $1 AND a.status = 'confirmed'
        ORDER BY a.confirmed_at DESC
        LIMIT 1
    """,
        row["id"],
    )

    if proof_row:
        proof_path = proof_row["proof_path"]
        if isinstance(proof_path, str):
            proof_path = _json.loads(proof_path)
        chain = proof_row["chain"]
        tx_hash = proof_row["tx_hash"]
        explorer_url = (
            f"https://polygonscan.com/tx/{tx_hash}"
            if chain == "polygon"
            else f"https://www.blockchain.com/btc/tx/{tx_hash}"
            if chain == "bitcoin"
            else None
        )
        response["blockchain"] = {
            "anchored": True,
            "chain": chain,
            "merkle_root": proof_row["merkle_root"],
            "tx_hash": tx_hash,
            "block_number": proof_row["block_number"],
            "anchored_at": proof_row["confirmed_at"].isoformat() if proof_row["confirmed_at"] else None,
            "explorer_url": explorer_url,
            "leaf_hash": proof_row["leaf_hash"],
            "merkle_proof": proof_path,
            "verify_instructions": (
                "Recompute root from leaf_hash + merkle_proof using SHA-256 "
                "pair-hashing (left-then-right order from each step). "
                "Compare to merkle_root and on-chain anchor at tx_hash."
            ),
        }
    else:
        response["blockchain"] = {
            "anchored": False,
            "note": "Anchor pending — typically within 24 hours of cert issuance.",
        }

    return response


@router.put("/certificates/{cert_id}/status")
async def update_cert_status(
    cert_id: str,
    req: dict,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Provider owner: suspend, revoke, or reactivate a certificate."""
    _validate_uuid(cert_id)
    if user["role"] != "provider" or not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức")

    new_status = req.get("status")
    if new_status not in ("active", "suspended", "revoked"):
        raise HTTPException(400, "Status: active | suspended | revoked")

    row = await db.fetchrow("SELECT * FROM halal_certificates WHERE id=$1 AND issued_by=$2", cert_id, user["sub"])
    if not row:
        raise HTTPException(404)

    if new_status == "revoked":
        # Strict revocation path — requires reason + records actor + atomic
        from services.cert_lifecycle import (
            AlreadyRevoked,
            InvalidRevocation,
            revoke_cert,
        )

        try:
            await revoke_cert(
                db,
                cert_id=cert_id,
                reason=req.get("reason", ""),
                revoked_by_user_id=user["sub"],
            )
        except InvalidRevocation as e:
            raise HTTPException(400, f"Cần có lý do khi thu hồi: {e}")
        except AlreadyRevoked:
            raise HTTPException(400, "Chứng nhận đã bị thu hồi trước đó")
    else:
        await db.execute("UPDATE halal_certificates SET status=$1 WHERE id=$2", new_status, cert_id)

    await log_audit(
        db,
        user=user,
        action="certificate.status_change",
        entity_type="certificate",
        entity_id=cert_id,
        changes={"status": [row["status"], new_status]},
        metadata={
            "cert_number": row["cert_number"],
            "reason": req.get("reason", ""),
        },
    )

    # Notify business
    from auth.notification_router import notify

    biz_owner = await db.fetchrow(
        "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", row["business_tenant"]
    )
    if biz_owner:
        labels = {"active": "được kích hoạt lại", "suspended": "bị tạm đình chỉ", "revoked": "bị thu hồi"}
        await notify(
            db,
            str(biz_owner["id"]),
            "certificate",
            f"Chứng nhận {row['cert_number']} đã {labels[new_status]}",
            req.get("reason", ""),
            "/documents",
        )

    return {"message": f"Đã cập nhật trạng thái: {new_status}"}


@router.get("/certificates/{cert_id}/pdf")
async def download_certificate_pdf(
    cert_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Connection = Depends(get_db),
):
    _validate_uuid(cert_id)

    # Support token from header or query param (for <a href> links)
    from auth.jwt_utils import decode_token

    auth = request.headers.get("Authorization", "")
    tk = auth[7:] if auth.startswith("Bearer ") else token
    if not tk:
        raise HTTPException(401, "Unauthorized")
    try:
        user = decode_token(tk)
    except Exception:
        raise HTTPException(401, "Invalid token")

    row = await db.fetchrow("SELECT * FROM halal_certificates WHERE id=$1", cert_id)
    if not row:
        raise HTTPException(404)

    # Access check
    if user["role"] == "provider" and str(row["issued_by"]) != user["sub"]:
        raise HTTPException(403)
    if user["role"] == "business" and str(row["business_tenant"]) != user.get("tenant_id"):
        raise HTTPException(403)

    if not row["pdf_path"]:
        raise HTTPException(404, "PDF chưa được tạo")

    from pathlib import Path

    pdf_file = Path(row["pdf_path"])
    if not pdf_file.exists():
        raise HTTPException(404, "File PDF không tồn tại")

    import urllib.parse

    encoded = urllib.parse.quote(f"{row['cert_number']}.pdf")
    return Response(
        content=pdf_file.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded}"},
    )
