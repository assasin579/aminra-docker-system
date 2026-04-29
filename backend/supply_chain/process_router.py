"""Process template CRUD — flowchart JSON storage + DOCX export."""

import logging
import json as _json
import io
from uuid import UUID as _UUID

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.permissions import check_permission_db
from .models import ProcessCreate, ProcessUpdate, ProcessOut

log = logging.getLogger("aminra.supply_chain.process")
router = APIRouter()


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


@router.get("/processes")
async def list_processes(user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    rows = await db.fetch("SELECT * FROM process_templates WHERE tenant_id=$1 ORDER BY updated_at DESC", tenant_id)
    return {
        "processes": [
            ProcessOut(
                id=str(r["id"]),
                name=r["name"],
                description=r["description"],
                flowchart=r["flowchart"] if isinstance(r["flowchart"], dict) else _json.loads(r["flowchart"]),
                version=r["version"],
                is_active=r["is_active"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
    }


@router.post("/processes")
async def create_process(req: ProcessCreate, user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    flowchart = _json.dumps(req.flowchart or {"nodes": [], "edges": []})
    row = await db.fetchrow(
        """
        INSERT INTO process_templates (tenant_id, name, description, flowchart)
        VALUES ($1,$2,$3,$4::jsonb) RETURNING id
    """,
        tenant_id,
        req.name,
        req.description,
        flowchart,
    )
    log.info(f"[process] Created {row['id']}")
    return {"id": str(row["id"]), "message": "Đã tạo quy trình"}


@router.get("/processes/{pid}")
async def get_process(pid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(pid)
    tenant_id = _require_business(user)
    row = await db.fetchrow("SELECT * FROM process_templates WHERE id=$1 AND tenant_id=$2", pid, tenant_id)
    if not row:
        raise HTTPException(404)
    fc = row["flowchart"]
    if isinstance(fc, str):
        fc = _json.loads(fc)
    return ProcessOut(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        flowchart=fc,
        version=row["version"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.put("/processes/{pid}")
async def update_process(pid: str, req: ProcessUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(pid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    updates, params, idx = [], [pid, tenant_id], 3
    if req.name is not None:
        updates.append(f"name = ${idx}")
        params.append(req.name)
        idx += 1
    if req.description is not None:
        updates.append(f"description = ${idx}")
        params.append(req.description)
        idx += 1
    if req.flowchart is not None:
        updates.append(f"flowchart = ${idx}::jsonb")
        params.append(_json.dumps(req.flowchart))
        idx += 1
        updates.append("version = version + 1")
    if req.is_active is not None:
        updates.append(f"is_active = ${idx}")
        params.append(req.is_active)
        idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    result = await db.execute(
        f"UPDATE process_templates SET {', '.join(updates)} WHERE id=$1 AND tenant_id=$2", *params
    )
    if result == "UPDATE 0":
        raise HTTPException(404)
    return {"message": "Đã cập nhật"}


@router.delete("/processes/{pid}")
async def delete_process(pid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(pid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_delete")
    result = await db.execute("DELETE FROM process_templates WHERE id=$1 AND tenant_id=$2", pid, tenant_id)
    if result == "DELETE 0":
        raise HTTPException(404)
    return {"message": "Đã xoá"}


@router.post("/processes/{pid}/export-docx")
async def export_process_docx(pid: str, user=Depends(get_current_user), db=Depends(get_db)):
    """Export process template as DOCX document."""
    _validate_uuid(pid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    row = await db.fetchrow("SELECT * FROM process_templates WHERE id=$1 AND tenant_id=$2", pid, tenant_id)
    if not row:
        raise HTTPException(404)

    fc = row["flowchart"]
    if isinstance(fc, str):
        fc = _json.loads(fc)

    # Get company name
    company = await db.fetchrow("SELECT company_name FROM users WHERE id=$1", tenant_id)
    company_name = company["company_name"] if company else "N/A"

    # Build DOCX
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from datetime import datetime

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    # Title
    title = doc.add_heading(f"QUY TRÌNH: {row['name']}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Meta info
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f"Công ty: {company_name}\n").bold = True
    meta.add_run(f"Phiên bản: {row['version']} · Ngày: {datetime.now().strftime('%d/%m/%Y')}\n")
    meta.add_run("")

    # Description
    if row["description"]:
        doc.add_heading("1. MỤC ĐÍCH", level=1)
        doc.add_paragraph(row["description"])

    # Steps
    nodes = fc.get("nodes", [])
    edges = fc.get("edges", [])

    # Topological sort for ordering
    sorted_nodes = sorted([n for n in nodes if n.get("type") == "main"], key=lambda n: n.get("order", 0))

    if sorted_nodes:
        doc.add_heading("2. CÁC BƯỚC THỰC HIỆN", level=1)

        for i, node in enumerate(sorted_nodes, 1):
            doc.add_heading(f"Bước {i}: {node.get('label', 'Không tên')}", level=2)

            if node.get("description"):
                doc.add_paragraph(f"Mô tả: {node['description']}")
            if node.get("standard"):
                doc.add_paragraph(f"Tiêu chuẩn: {node['standard']}")
            if node.get("responsible"):
                doc.add_paragraph(f"Người phụ trách: {node['responsible']}")
            if node.get("duration"):
                doc.add_paragraph(f"Thời gian: {node['duration']}")
            if node.get("equipment"):
                doc.add_paragraph(f"Thiết bị: {node['equipment']}")
            if node.get("conditions"):
                doc.add_paragraph(f"Điều kiện: {node['conditions']}")

            checklist = node.get("checklist", [])
            if checklist:
                doc.add_paragraph("Checklist Halal:")
                for item in checklist:
                    if isinstance(item, str):
                        doc.add_paragraph(f"☐ {item}", style="List Bullet")
                    elif isinstance(item, dict):
                        doc.add_paragraph(f"☐ {item.get('text', '')}", style="List Bullet")

            if node.get("notes"):
                doc.add_paragraph(f"Ghi chú: {node['notes']}")

            # Sub-steps
            children_ids = node.get("children", [])
            sub_nodes = [n for n in nodes if n.get("id") in children_ids]
            for j, sub in enumerate(sub_nodes, 1):
                p = doc.add_paragraph()
                p.add_run(f"  Bước {i}.{j}: {sub.get('label', '')}").bold = True
                if sub.get("description"):
                    doc.add_paragraph(f"    {sub['description']}")

            # Check for parallel edges
            parallel_targets = [
                e["to"] for e in edges if e.get("from") == node.get("id") and e.get("type") == "parallel"
            ]
            if parallel_targets:
                p = doc.add_paragraph()
                p.add_run("→ Thực hiện song song:").italic = True
                for pid_target in parallel_targets:
                    target_node = next((n for n in nodes if n.get("id") == pid_target), None)
                    if target_node:
                        doc.add_paragraph(f"  ├── {target_node.get('label', '')}", style="List Bullet")

    # Approval section
    doc.add_heading("3. PHÊ DUYỆT", level=1)
    table = doc.add_table(rows=2, cols=3)
    table.style = "Table Grid"
    for cell in table.rows[0].cells:
        for p in cell.paragraphs:
            p.style.font.size = Pt(10)
    table.rows[0].cells[0].text = "Vai trò"
    table.rows[0].cells[1].text = "Họ tên"
    table.rows[0].cells[2].text = "Ngày / Chữ ký"
    table.rows[1].cells[0].text = "Người lập"
    table.rows[1].cells[1].text = ""
    table.rows[1].cells[2].text = ""

    # Save to buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    import urllib.parse

    safe_name = row["name"].replace(" ", "_")[:50]
    encoded_name = urllib.parse.quote(f"QuyTrinh_{safe_name}.docx")
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )
