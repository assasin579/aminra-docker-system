"""Halal Certificate issuance — generate cert PDF after submission approval."""

import logging
import io
from datetime import date, timedelta
from typing import Optional
from uuid import UUID as _UUID

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from asyncpg import Connection

from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.notification_router import notify

log = logging.getLogger("aminra.certificates")
router = APIRouter()


def _validate_uuid(v: str) -> str:
    try: _UUID(v)
    except ValueError: raise HTTPException(400, "Invalid ID")
    return v


class IssueCertRequest(BaseModel):
    expiry_months: int = 12
    notes: str = ""


@router.post("/received/{submission_id}/issue-certificate")
async def issue_certificate(
    submission_id: str,
    req: IssueCertRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Provider owner issues Halal certificate after approving a submission."""
    _validate_uuid(submission_id)
    if user["role"] != "provider" or not user.get("is_owner"):
        raise HTTPException(403, "Chỉ chủ tổ chức mới được cấp chứng nhận")

    sub = await db.fetchrow(
        "SELECT * FROM submissions WHERE id=$1 AND provider_id=$2", submission_id, user["sub"])
    if not sub:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    if sub["status"] != "approved":
        raise HTTPException(400, "Chỉ có thể cấp chứng nhận cho hồ sơ đã được duyệt")

    # Check if cert already issued
    existing = await db.fetchrow(
        "SELECT id, cert_number FROM halal_certificates WHERE submission_id=$1 AND status='active'", submission_id)
    if existing:
        raise HTTPException(400, f"Chứng nhận đã được cấp: {existing['cert_number']}")

    # Generate cert number: HALAL-YYYY-NNNN
    year = date.today().year
    count = await db.fetchval(
        "SELECT COUNT(*) FROM halal_certificates WHERE cert_number LIKE $1", f"HALAL-{year}-%")
    cert_number = f"HALAL-{year}-{(count or 0) + 1:04d}"

    issue_date = date.today()
    expiry_date = date(issue_date.year + req.expiry_months // 12,
                       issue_date.month + req.expiry_months % 12 if issue_date.month + req.expiry_months % 12 <= 12 else (issue_date.month + req.expiry_months % 12) - 12,
                       min(issue_date.day, 28))
    if issue_date.month + req.expiry_months % 12 > 12:
        expiry_date = expiry_date.replace(year=expiry_date.year + 1)

    # Get names
    provider = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", user["sub"])
    provider_name = provider["company_name"] if provider else "N/A"
    business_name = sub["company_name"] or "N/A"

    # Generate PDF
    pdf_path = None
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont('VNFont', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('VNFontBold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=30*mm, bottomMargin=30*mm,
                                leftMargin=25*mm, rightMargin=25*mm)

        title_style = ParagraphStyle('Title', fontName='VNFontBold', fontSize=22, leading=28,
                                     alignment=TA_CENTER, textColor=colors.HexColor('#065E43'))
        sub_style = ParagraphStyle('Sub', fontName='VNFont', fontSize=11, leading=16,
                                   alignment=TA_CENTER, textColor=colors.HexColor('#374151'))
        body_style = ParagraphStyle('Body', fontName='VNFont', fontSize=11, leading=16,
                                    textColor=colors.HexColor('#1A2332'))
        bold_style = ParagraphStyle('Bold', fontName='VNFontBold', fontSize=11, leading=16,
                                    textColor=colors.HexColor('#1A2332'))

        elements = []
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph("CHỨNG NHẬN HALAL", title_style))
        elements.append(Paragraph("HALAL CERTIFICATE", sub_style))
        elements.append(Spacer(1, 8*mm))

        # Certificate details
        elements.append(Paragraph(f"<b>Số chứng nhận:</b> {cert_number}", body_style))
        elements.append(Spacer(1, 3*mm))

        info = [
            ['Doanh nghiệp', business_name],
            ['Tổ chức cấp', provider_name],
            ['Ngày cấp', issue_date.strftime('%d/%m/%Y')],
            ['Ngày hết hạn', expiry_date.strftime('%d/%m/%Y')],
        ]
        if req.notes:
            info.append(['Ghi chú', req.notes])

        info_table = Table(info, colWidths=[45*mm, 115*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'VNFontBold'),
            ('FONTNAME', (1, 0), (1, -1), 'VNFont'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 15*mm))

        elements.append(Paragraph(
            "Chứng nhận này xác nhận rằng doanh nghiệp nêu trên đã hoàn thành đánh giá "
            "và đáp ứng các yêu cầu về tiêu chuẩn Halal theo quy trình kiểm định của tổ chức cấp.",
            body_style))
        elements.append(Spacer(1, 20*mm))

        # Signature area
        sig_table = Table([
            ['Đại diện tổ chức cấp', '', 'Ngày cấp'],
            ['', '', issue_date.strftime('%d/%m/%Y')],
            ['_' * 30, '', '_' * 20],
            [provider_name, '', ''],
        ], colWidths=[80*mm, 20*mm, 60*mm])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'VNFont'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(sig_table)

        elements.append(Spacer(1, 15*mm))
        footer_style = ParagraphStyle('Footer', fontName='VNFont', fontSize=8, leading=11,
                                      alignment=TA_CENTER, textColor=colors.HexColor('#94A3B8'))
        elements.append(Paragraph(f"Chứng nhận được tạo tự động bởi AMINRA · {cert_number}", footer_style))

        doc.build(elements)
        buf.seek(0)

        # Save PDF
        from pathlib import Path
        save_dir = Path("docs") / "certificates"
        save_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = save_dir / f"{cert_number}.pdf"
        pdf_file.write_bytes(buf.getvalue())
        pdf_path = str(pdf_file)

    except Exception as e:
        log.warning(f"[cert] PDF generation failed: {e}")

    # Insert certificate record
    row = await db.fetchrow("""
        INSERT INTO halal_certificates (submission_id, cert_number, issued_by, business_tenant, company_name,
                                        issue_date, expiry_date, pdf_path, notes)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
    """, submission_id, cert_number, user["sub"], sub["business_tenant"], business_name,
        issue_date, expiry_date, pdf_path, req.notes)

    log.info(f"[cert] Issued {cert_number} for submission {submission_id}")

    # Notify business owner
    biz_owner = await db.fetchrow(
        "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", sub["business_tenant"])
    if biz_owner:
        await notify(db, str(biz_owner["id"]), "certificate",
                     f"Chứng nhận Halal đã được cấp: {cert_number}",
                     f"Có hiệu lực đến {expiry_date.strftime('%d/%m/%Y')}",
                     "/dashboard/business")

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
            "SELECT * FROM halal_certificates WHERE issued_by=$1 ORDER BY created_at DESC", user["sub"])
    elif user["role"] == "business":
        rows = await db.fetch(
            "SELECT * FROM halal_certificates WHERE business_tenant=$1 ORDER BY created_at DESC",
            user.get("tenant_id"))
    else:
        return {"certificates": []}

    return {"certificates": [
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
        } for r in rows
    ]}


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
    stats = await db.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='active') AS active,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date < NOW() + INTERVAL '90 days') AS expiring_soon,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date < NOW()) AS expired,
            COUNT(*) FILTER (WHERE status='suspended') AS suspended,
            COUNT(*) FILTER (WHERE status='revoked') AS revoked
        FROM halal_certificates WHERE issued_by=$1
    """, provider_id)

    # Filtered list
    where = "c.issued_by=$1"
    params = [provider_id]
    idx = 2
    if status:
        if status == 'expiring':
            where += f" AND c.status='active' AND c.expiry_date < NOW() + INTERVAL '90 days'"
        elif status == 'expired':
            where += f" AND c.status='active' AND c.expiry_date < NOW()"
        else:
            where += f" AND c.status=${idx}"
            params.append(status); idx += 1
    if expiring_days > 0:
        where += f" AND c.status='active' AND c.expiry_date < NOW() + INTERVAL '{int(expiring_days)} days'"

    rows = await db.fetch(f"""
        SELECT c.*, u.company_name AS provider_name
        FROM halal_certificates c
        LEFT JOIN users u ON u.id=c.issued_by
        WHERE {where}
        ORDER BY c.expiry_date ASC
    """, *params)

    return {
        "stats": {
            "total": stats["total"], "active": stats["active"],
            "expiring_soon": stats["expiring_soon"], "expired": stats["expired"],
            "suspended": stats["suspended"], "revoked": stats["revoked"],
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
            } for r in rows
        ],
    }


@router.get("/certificates/public/{cert_number}")
async def public_verify_cert(cert_number: str, db: Connection = Depends(get_db)):
    """Public endpoint — NO AUTH. Verify a certificate by its number."""
    row = await db.fetchrow("""
        SELECT c.cert_number, c.company_name, c.issue_date, c.expiry_date, c.status,
               u.company_name AS provider_name
        FROM halal_certificates c
        LEFT JOIN users u ON u.id=c.issued_by
        WHERE c.cert_number=$1
    """, cert_number.strip().upper())
    if not row:
        raise HTTPException(404, "Chứng nhận không tồn tại")

    is_expired = row["expiry_date"] < date.today() if row["expiry_date"] else False
    effective_status = "expired" if is_expired and row["status"] == "active" else row["status"]

    return {
        "cert_number": row["cert_number"],
        "company_name": row["company_name"],
        "provider_name": row["provider_name"],
        "issue_date": row["issue_date"].isoformat(),
        "expiry_date": row["expiry_date"].isoformat(),
        "status": effective_status,
        "valid": effective_status == "active" and not is_expired,
    }


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

    await db.execute("UPDATE halal_certificates SET status=$1 WHERE id=$2", new_status, cert_id)

    # Notify business
    from auth.notification_router import notify
    biz_owner = await db.fetchrow(
        "SELECT id FROM users WHERE (id=$1 OR tenant_id=$1) AND is_owner=true LIMIT 1", row["business_tenant"])
    if biz_owner:
        labels = {"active": "được kích hoạt lại", "suspended": "bị tạm đình chỉ", "revoked": "bị thu hồi"}
        await notify(db, str(biz_owner["id"]), "certificate",
                     f"Chứng nhận {row['cert_number']} đã {labels[new_status]}",
                     req.get("reason", ""), "/documents")

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
