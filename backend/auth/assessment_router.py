"""Self-Assessment — Business users evaluate their own readiness before CB audit."""

import logging
import io
import json as _json
from uuid import UUID as _UUID
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from asyncpg import Connection

from auth.db import get_db
from auth.jwt_utils import get_current_user

log = logging.getLogger("aminra.assessments")
router = APIRouter()


def _validate_uuid(v: str) -> str:
    try: _UUID(v)
    except ValueError: raise HTTPException(400, "Invalid ID")
    return v


def _require_business(user: dict):
    if user.get("role") != "business":
        raise HTTPException(403, "Chỉ dành cho doanh nghiệp")
    return user.get("tenant_id")


# ── List available templates (from CB) ──

@router.get("/templates")
async def list_assessment_templates(user=Depends(get_current_user), db=Depends(get_db)):
    """Business user: list all published audit checklist templates."""
    _require_business(user)
    rows = await db.fetch("""
        SELECT t.id, t.name, t.standard, t.items, u.company_name AS provider_name
        FROM audit_checklist_templates t
        LEFT JOIN users u ON u.id = t.provider_id
        ORDER BY t.name
    """)
    return {"templates": [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "standard": r["standard"],
            "provider_name": r["provider_name"] or "N/A",
            "item_count": len(r["items"]) if isinstance(r["items"], list) else len(_json.loads(r["items"])) if isinstance(r["items"], str) else 0,
        } for r in rows
    ]}


# ── CRUD Assessments ──

@router.get("/")
async def list_assessments(user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    rows = await db.fetch(
        "SELECT * FROM self_assessments WHERE tenant_id=$1 ORDER BY created_at DESC", tenant_id)
    return {"assessments": [
        {
            "id": str(r["id"]),
            "name": r["name"] or r["standard"] or "Đánh giá",
            "standard": r["standard"],
            "status": r["status"],
            "score": r["score"],
            "total_items": r["total_items"],
            "passed_items": r["passed_items"],
            "created_at": r["created_at"].isoformat(),
        } for r in rows
    ]}


class CreateAssessment(BaseModel):
    template_id: str
    name: str = ""


@router.post("/")
async def create_assessment(req: CreateAssessment, user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    _validate_uuid(req.template_id)

    # Get template
    tmpl = await db.fetchrow("SELECT * FROM audit_checklist_templates WHERE id=$1", req.template_id)
    if not tmpl:
        raise HTTPException(404, "Template không tồn tại")

    items = tmpl["items"]
    if isinstance(items, str):
        items = _json.loads(items)

    # Add result/note fields to each item
    assessment_items = []
    for item in items:
        assessment_items.append({
            **item,
            "result": None,  # pass / fail / na
            "note": "",
        })

    name = req.name or tmpl["name"]
    row = await db.fetchrow("""
        INSERT INTO self_assessments (tenant_id, template_id, standard, name, items, total_items)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6) RETURNING id
    """, tenant_id, req.template_id, tmpl["standard"], name,
        _json.dumps(assessment_items), len(assessment_items))

    return {"id": str(row["id"]), "message": f"Đã tạo đánh giá: {name}"}


@router.get("/{aid}")
async def get_assessment(aid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(aid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT * FROM self_assessments WHERE id=$1 AND tenant_id=$2", aid, tenant_id)
    if not row:
        raise HTTPException(404)

    items = row["items"]
    if isinstance(items, str):
        items = _json.loads(items)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "standard": row["standard"],
        "status": row["status"],
        "score": row["score"],
        "total_items": row["total_items"],
        "passed_items": row["passed_items"],
        "items": items,
        "created_at": row["created_at"].isoformat(),
    }


@router.put("/{aid}/items/{index}")
async def update_assessment_item(aid: str, index: int, req: dict,
                                  user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(aid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT items FROM self_assessments WHERE id=$1 AND tenant_id=$2", aid, tenant_id)
    if not row:
        raise HTTPException(404)

    items = row["items"]
    if isinstance(items, str):
        items = _json.loads(items)

    if index < 0 or index >= len(items):
        raise HTTPException(400, "Index không hợp lệ")

    if "result" in req:
        if req["result"] not in ("pass", "fail", "na", None):
            raise HTTPException(400, "result: pass | fail | na")
        items[index]["result"] = req["result"]
    if "note" in req:
        items[index]["note"] = req["note"]

    await db.execute("UPDATE self_assessments SET items=$1::jsonb WHERE id=$2",
                     _json.dumps(items), aid)
    return {"message": "OK"}


@router.post("/{aid}/complete")
async def complete_assessment(aid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(aid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT items FROM self_assessments WHERE id=$1 AND tenant_id=$2", aid, tenant_id)
    if not row:
        raise HTTPException(404)

    items = row["items"]
    if isinstance(items, str):
        items = _json.loads(items)

    total = len(items)
    passed = sum(1 for i in items if i.get("result") == "pass")
    answered = sum(1 for i in items if i.get("result") and i["result"] != "na")
    score = round(passed / answered * 100) if answered > 0 else 0

    await db.execute("""
        UPDATE self_assessments SET status='completed', score=$1, passed_items=$2, total_items=$3 WHERE id=$4
    """, score, passed, total, aid)

    return {"message": "Đã hoàn thành đánh giá", "score": score, "passed": passed, "total": total}


@router.delete("/{aid}")
async def delete_assessment(aid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(aid)
    tenant_id = _require_business(user)
    await db.execute("DELETE FROM self_assessments WHERE id=$1 AND tenant_id=$2", aid, tenant_id)
    return {"message": "Đã xóa"}


# ── Export Gap Analysis PDF ──

@router.get("/{aid}/export-pdf")
async def export_gap_pdf(aid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(aid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT * FROM self_assessments WHERE id=$1 AND tenant_id=$2", aid, tenant_id)
    if not row:
        raise HTTPException(404)

    items = row["items"]
    if isinstance(items, str):
        items = _json.loads(items)

    # Get company name
    company = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", tenant_id)
    company_name = company["company_name"] if company else "N/A"

    total = len(items)
    passed = sum(1 for i in items if i.get("result") == "pass")
    failed = sum(1 for i in items if i.get("result") == "fail")
    na = sum(1 for i in items if i.get("result") == "na")
    score = row["score"] or 0
    gaps = [i for i in items if i.get("result") == "fail" or not i.get("result")]

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
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=25*mm, bottomMargin=25*mm, leftMargin=20*mm, rightMargin=20*mm)

    title_s = ParagraphStyle('T', fontName='VNFontBold', fontSize=18, leading=24, alignment=TA_CENTER, textColor=colors.HexColor('#065E43'))
    h2_s = ParagraphStyle('H2', fontName='VNFontBold', fontSize=13, leading=18, textColor=colors.HexColor('#1A2332'))
    body_s = ParagraphStyle('B', fontName='VNFont', fontSize=10, leading=14, textColor=colors.HexColor('#374151'))

    elements = []
    elements.append(Paragraph("BÁO CÁO TỰ ĐÁNH GIÁ HALAL", title_s))
    elements.append(Paragraph("SELF-ASSESSMENT GAP ANALYSIS", ParagraphStyle('Sub', fontName='VNFont', fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor('#6B7280'))))
    elements.append(Spacer(1, 8*mm))

    info = [["Doanh nghiệp", company_name], ["Tiêu chuẩn", row["standard"] or "N/A"],
            ["Điểm đạt", f"{score}%"], ["Đạt/Tổng", f"{passed}/{total}"],
            ["Chưa đạt", str(failed)], ["N/A", str(na)]]
    t = Table(info, colWidths=[40*mm, 130*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'VNFontBold'), ('FONTNAME', (1,0), (1,-1), 'VNFont'),
        ('FONTSIZE', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))

    if gaps:
        elements.append(Paragraph(f"CÁC HẠNG MỤC CẦN CẢI THIỆN ({len(gaps)})", h2_s))
        elements.append(Spacer(1, 3*mm))
        for idx, g in enumerate(gaps, 1):
            sev = g.get("severity", "minor")
            sev_label = {"critical": "Nghiêm trọng", "major": "Lớn", "minor": "Nhỏ"}.get(sev, sev)
            elements.append(Paragraph(
                f'<b>{idx}. [{sev_label}] {g.get("code", "")} — {g.get("criteria", "")}</b>', body_s))
            if g.get("clause"):
                elements.append(Paragraph(f'   Điều khoản: {g["clause"]}', body_s))
            if g.get("documents"):
                elements.append(Paragraph(f'   Tài liệu cần: {g["documents"]}', body_s))
            if g.get("note"):
                elements.append(Paragraph(f'   Ghi chú: {g["note"]}', body_s))
            elements.append(Spacer(1, 2*mm))

    elements.append(Spacer(1, 10*mm))
    footer_s = ParagraphStyle('F', fontName='VNFont', fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor('#94A3B8'))
    elements.append(Paragraph(f"Báo cáo tạo tự động bởi AMINRA · {company_name}", footer_s))

    doc.build(elements)
    buf.seek(0)

    import urllib.parse
    fname = urllib.parse.quote(f"SelfAssessment_{row['standard'] or 'report'}.pdf")
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
