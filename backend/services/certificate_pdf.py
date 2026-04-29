"""Halal certificate PDF generator.

Inputs are validated; on bad input we raise ValueError so the calling
endpoint surfaces a 4xx instead of silently issuing a cert without a PDF.
The cert hash + QR code give the public verifier two independent
ways to confirm authenticity.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import date

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ── Data ────────────────────────────────────────────────────────────────────


@dataclass
class CertificateData:
    cert_number: str
    business_name: str
    provider_name: str
    issue_date: date
    expiry_date: date
    verify_url: str
    notes: str = ""


def _validate(cert: CertificateData) -> None:
    if not cert.cert_number:
        raise ValueError("cert_number is required")
    if not cert.verify_url:
        raise ValueError("verify_url is required (used in embedded QR)")
    if cert.expiry_date <= cert.issue_date:
        raise ValueError("expiry_date must be after issue_date")


# ── Tamper-detection hash ───────────────────────────────────────────────────
# SHA-256 of canonical newline-joined fields. The same hash is rendered in
# the PDF footer; an offline verifier (or future API) can recompute and
# compare to detect tampering.


def compute_cert_hash(cert: CertificateData) -> str:
    fields = [
        cert.cert_number,
        cert.business_name,
        cert.provider_name,
        cert.issue_date.isoformat(),
        cert.expiry_date.isoformat(),
        cert.notes,
        cert.verify_url,
    ]
    canonical = "\n".join(fields).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ── QR ──────────────────────────────────────────────────────────────────────
# Deterministic settings → unit tests can regenerate the same PNG bytes.

_QR_SETTINGS = dict(
    version=1,
    error_correction=ERROR_CORRECT_M,
    box_size=8,
    border=2,
)


def _build_qr_png(payload: str) -> bytes:
    qr = qrcode.QRCode(**_QR_SETTINGS)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Fonts (registered once per process) ────────────────────────────────────

_FONT_REGISTERED = False
_DEJAVU_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _register_fonts() -> None:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("VNFont", _DEJAVU_REG))
    pdfmetrics.registerFont(TTFont("VNFontBold", _DEJAVU_BOLD))
    _FONT_REGISTERED = True


# ── PDF ─────────────────────────────────────────────────────────────────────


def generate_pdf(cert: CertificateData) -> bytes:
    _validate(cert)
    _register_fonts()

    cert_hash = compute_cert_hash(cert)
    qr_png = _build_qr_png(cert.verify_url)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    title_style = ParagraphStyle(
        "Title",
        fontName="VNFontBold",
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#065E43"),
    )
    sub_style = ParagraphStyle(
        "Sub",
        fontName="VNFont",
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#374151"),
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="VNFont",
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#1A2332"),
    )
    footer_style = ParagraphStyle(
        "Footer",
        fontName="VNFont",
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#94A3B8"),
    )
    cert_no_style = ParagraphStyle(
        "CertNo",
        fontName="VNFontBold",
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#065E43"),
    )

    elements = []
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph("CHỨNG NHẬN HALAL", title_style))
    elements.append(Paragraph("HALAL CERTIFICATE", sub_style))
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(f"Số chứng nhận / Cert No: {cert.cert_number}", cert_no_style))
    elements.append(Spacer(1, 6 * mm))

    info_rows = [
        ["Doanh nghiệp / Business", cert.business_name],
        ["Tổ chức cấp / Issued by", cert.provider_name],
        ["Ngày cấp / Issue date", cert.issue_date.strftime("%d/%m/%Y")],
        ["Ngày hết hạn / Expiry", cert.expiry_date.strftime("%d/%m/%Y")],
    ]
    if cert.notes:
        info_rows.append(["Ghi chú / Notes", cert.notes])

    info_table = Table(info_rows, colWidths=[55 * mm, 110 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "VNFontBold"),
                ("FONTNAME", (1, 0), (1, -1), "VNFont"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 10 * mm))

    elements.append(
        Paragraph(
            "Chứng nhận này xác nhận rằng doanh nghiệp nêu trên đã hoàn thành đánh giá "
            "và đáp ứng các yêu cầu về tiêu chuẩn Halal theo quy trình kiểm định của tổ chức cấp.",
            body_style,
        )
    )
    elements.append(Spacer(1, 6 * mm))
    elements.append(
        Paragraph(
            "<i>This certificate confirms the named business has completed the audit "
            "and meets the Halal standards as evaluated by the issuing body.</i>",
            body_style,
        )
    )
    elements.append(Spacer(1, 12 * mm))

    # QR + signature row
    qr_image = Image(io.BytesIO(qr_png), width=35 * mm, height=35 * mm)
    qr_caption = Paragraph(
        "Quét mã QR để xác minh<br/>Scan to verify",
        ParagraphStyle("QRCap", fontName="VNFont", fontSize=8, leading=11, alignment=TA_CENTER),
    )
    qr_cell = Table([[qr_image], [qr_caption]], colWidths=[40 * mm])
    qr_cell.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))

    sig_lines = [
        ["Đại diện tổ chức cấp", "", ""],
        ["Issuing body representative", "", ""],
        ["", "", ""],
        ["_" * 32, "", cert.issue_date.strftime("%d/%m/%Y")],
        [cert.provider_name, "", ""],
    ]
    sig_table = Table(sig_lines, colWidths=[80 * mm, 10 * mm, 35 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "VNFont"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    bottom_row = Table([[sig_table, qr_cell]], colWidths=[125 * mm, 40 * mm])
    bottom_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(bottom_row)

    elements.append(Spacer(1, 10 * mm))
    elements.append(
        Paragraph(
            f"Hash: {cert_hash[:16]}… · Verify: {cert.verify_url}",
            footer_style,
        )
    )
    elements.append(
        Paragraph(
            f"Generated by AMINRA · {cert.cert_number}",
            footer_style,
        )
    )

    doc.build(elements)
    return buf.getvalue()
