"""
Document management API — list, detail, delete tenant documents.
"""
import json as _json
import logging
from typing import Optional
from datetime import datetime

from uuid import UUID as _UUID

import os
from pathlib import Path as _Path

from fastapi import APIRouter, HTTPException, Depends, Query, Request, UploadFile, File, Form
from fastapi.responses import FileResponse as _FileResponse
from pydantic import BaseModel
from uuid import uuid4 as _uuid4

from auth.db import get_db
from auth.jwt_utils import get_current_user, decode_token
from auth.upload_utils import validate_upload
from auth.permissions import check_permission_db

UPLOAD_DIR = _Path(os.getenv("UPLOAD_DIR", "./docs"))


def _get_user_from_header_or_query(request: Request, token: str | None) -> dict:
    """Try Authorization header first, then fall back to ?token= query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_token(auth[7:])
    if token:
        return decode_token(token)
    raise HTTPException(401, "Not authenticated")


def _validate_uuid(value: str) -> str:
    try:
        _UUID(value)
    except ValueError:
        raise HTTPException(400, "Invalid ID format")
    return value

log = logging.getLogger("aminra.documents")
router = APIRouter()


# ── Response models ────────────────────────────────────────────────────────────

class DocumentItem(BaseModel):
    id: str
    original_filename: str
    doc_type: Optional[str]
    doc_type_label: Optional[str]
    compliance_score: Optional[int]
    overall_status: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    uploaded_by_name: Optional[str]
    uploaded_at: datetime
    revision_count: Optional[int] = None
    status: Optional[str] = None

class DocumentDetail(DocumentItem):
    evaluation_result: Optional[dict]
    summary: Optional[str]
    issues: list = []
    strengths: list = []
    recommendations: list = []

class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int
    page: int
    page_size: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_result(raw) -> Optional[dict]:
    """asyncpg returns JSONB as str or dict depending on version."""
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return _json.loads(raw)
        except Exception:
            return None
    return raw

def _status_from_result(result: Optional[dict]) -> Optional[str]:
    if not result:
        return None
    return result.get("overall_status")

def _label_from_result(result: Optional[dict]) -> Optional[str]:
    if not result:
        return None
    return result.get("doc_type_label")


# ── Routes ─────────────────────────────────────────────────────────────────────

class RevisionItem(BaseModel):
    id: str
    original_filename: str
    compliance_score: Optional[int]
    overall_status: Optional[str]
    file_size: Optional[int]
    uploaded_by_name: Optional[str]
    uploaded_at: datetime

class RevisionListResponse(BaseModel):
    doc_type: str
    doc_type_label: Optional[str]
    revisions: list[RevisionItem]
    total: int


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),    # compliant | needs_review | non_compliant
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Return only the latest document per doc_type for the tenant."""
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "Tenant không xác định")

    offset = (page - 1) * page_size

    # CTE: pick the latest document per doc_type
    # Documents without doc_type each count as their own group (use id as fallback)
    cte = """
        WITH latest AS (
            SELECT DISTINCT ON (COALESCE(doc_type, id::text))
                   d.id, d.original_filename, d.doc_type, d.compliance_score,
                   d.file_size, d.mime_type, d.uploaded_at, d.evaluation_result,
                   d.user_id, d.tenant_id, d.status
            FROM documents d
            WHERE d.tenant_id = $1
            ORDER BY COALESCE(doc_type, id::text), d.uploaded_at DESC
        )
    """

    # Build dynamic WHERE on the CTE result
    conditions: list[str] = []
    params: list = [tenant_id]
    idx = 2

    if doc_type:
        conditions.append(f"l.doc_type = ${idx}")
        params.append(doc_type)
        idx += 1

    if status:
        conditions.append(f"l.evaluation_result->>'overall_status' = ${idx}")
        params.append(status)
        idx += 1

    extra_where = (" AND " + " AND ".join(conditions)) if conditions else ""

    total_row = await db.fetchrow(
        f"{cte} SELECT COUNT(*) FROM latest l WHERE true{extra_where}", *params
    )
    total = total_row["count"]

    rows = await db.fetch(
        f"""
        {cte}
        SELECT l.id, l.original_filename, l.doc_type, l.compliance_score,
               l.file_size, l.mime_type, l.uploaded_at, l.evaluation_result, l.status,
               u.company_name AS uploaded_by_name,
               (SELECT COUNT(*) FROM documents d2
                WHERE d2.tenant_id = $1
                  AND d2.doc_type IS NOT NULL
                  AND d2.doc_type = l.doc_type) AS revision_count
        FROM latest l
        LEFT JOIN users u ON u.id = l.user_id
        WHERE true{extra_where}
        ORDER BY l.uploaded_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *params, page_size, offset,
    )

    items = [
        DocumentItem(
            id=str(r["id"]),
            original_filename=r["original_filename"],
            doc_type=r["doc_type"],
            doc_type_label=_label_from_result(_parse_result(r["evaluation_result"])),
            compliance_score=r["compliance_score"],
            overall_status=_status_from_result(_parse_result(r["evaluation_result"])),
            file_size=r["file_size"],
            mime_type=r["mime_type"],
            uploaded_by_name=r["uploaded_by_name"],
            uploaded_at=r["uploaded_at"],
            revision_count=r["revision_count"],
            status=r["status"],
        )
        for r in rows
    ]

    return DocumentListResponse(
        documents=items, total=total, page=page, page_size=page_size
    )


@router.get("/documents/revisions/{doc_type_id}")
async def list_revisions(
    doc_type_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """List all revisions (uploads) for a specific doc_type within the tenant."""
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "Tenant không xác định")

    rows = await db.fetch(
        """
        SELECT d.id, d.original_filename, d.compliance_score,
               d.file_size, d.uploaded_at, d.evaluation_result,
               u.company_name AS uploaded_by_name
        FROM documents d
        LEFT JOIN users u ON u.id = d.user_id
        WHERE d.tenant_id = $1 AND d.doc_type = $2
        ORDER BY d.uploaded_at DESC
        """,
        tenant_id, doc_type_id,
    )

    doc_type_label = None
    revisions = []
    for r in rows:
        er = _parse_result(r["evaluation_result"])
        if not doc_type_label:
            doc_type_label = _label_from_result(er)
        revisions.append(RevisionItem(
            id=str(r["id"]),
            original_filename=r["original_filename"],
            compliance_score=r["compliance_score"],
            overall_status=_status_from_result(er),
            file_size=r["file_size"],
            uploaded_by_name=r["uploaded_by_name"],
            uploaded_at=r["uploaded_at"],
        ))

    return RevisionListResponse(
        doc_type=doc_type_id,
        doc_type_label=doc_type_label,
        revisions=revisions,
        total=len(revisions),
    )


@router.post("/documents/{doc_id}/promote")
async def promote_document(
    doc_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Promote a revision to be the current/active version for its doc_type."""
    _validate_uuid(doc_id)
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    tenant_id = user.get("tenant_id")
    row = await db.fetchrow(
        "SELECT id, doc_type FROM documents WHERE id = $1 AND tenant_id = $2",
        doc_id, tenant_id,
    )
    if not row:
        raise HTTPException(404, "Tài liệu không tồn tại")

    # Set uploaded_at to NOW() — makes this the "latest" version
    await db.execute(
        "UPDATE documents SET uploaded_at = NOW() WHERE id = $1",
        doc_id,
    )

    log.info(f"[documents] Promoted {doc_id} (type={row['doc_type']}) by {user['sub']}")
    return {"message": "Đã chọn phiên bản này làm tài liệu chính thức"}


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    _validate_uuid(doc_id)
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    tenant_id = user.get("tenant_id")
    row = await db.fetchrow(
        """
        SELECT d.id, d.original_filename, d.doc_type, d.compliance_score,
               d.file_size, d.mime_type, d.uploaded_at, d.evaluation_result,
               u.company_name AS uploaded_by_name
        FROM documents d
        LEFT JOIN users u ON u.id = d.user_id
        WHERE d.id = $1 AND d.tenant_id = $2
        """,
        doc_id, tenant_id,
    )

    if not row:
        raise HTTPException(404, "Tài liệu không tồn tại")

    er = _parse_result(row["evaluation_result"]) or {}
    return DocumentDetail(
        id=str(row["id"]),
        original_filename=row["original_filename"],
        doc_type=row["doc_type"],
        doc_type_label=er.get("doc_type_label"),
        compliance_score=row["compliance_score"],
        overall_status=er.get("overall_status"),
        file_size=row["file_size"],
        mime_type=row["mime_type"],
        uploaded_by_name=row["uploaded_by_name"],
        uploaded_at=row["uploaded_at"],
        evaluation_result=er,
        summary=er.get("summary"),
        issues=er.get("issues", []),
        strengths=er.get("strengths", []),
        recommendations=er.get("recommendations", []),
    )


@router.get("/documents/{doc_id}/preview")
async def preview_document(
    doc_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db=Depends(get_db),
):
    """Convert document to PDF for inline viewing. Caches the result."""
    user = _get_user_from_header_or_query(request, token)
    _validate_uuid(doc_id)
    row = None
    if user["role"] == "business":
        row = await db.fetchrow(
            "SELECT file_path, original_filename, mime_type FROM documents WHERE id = $1 AND tenant_id = $2",
            doc_id, user.get("tenant_id"),
        )
    elif user["role"] == "provider":
        # Provider/auditor can view docs in submissions OR revisions of docs in submissions
        row = await db.fetchrow(
            """SELECT d.file_path, d.original_filename, d.mime_type FROM documents d
               WHERE d.id = $1 AND EXISTS (
                   SELECT 1 FROM submissions s
                   WHERE (s.provider_id = $2 OR s.auditor_id = $2)
                   AND (
                       $1 = ANY(s.document_ids)
                       OR d.tenant_id = s.business_tenant
                   )
               )""",
            doc_id, user["sub"],
        )
    if not row:
        raise HTTPException(404, "Tài liệu không tồn tại")

    file_path = _Path(row["file_path"]) if row["file_path"] else None
    if not file_path or not file_path.exists():
        raise HTTPException(404, "File không tồn tại trên hệ thống")

    mime = row["mime_type"] or ""

    # If already PDF, serve directly
    if mime == "application/pdf" or file_path.suffix.lower() == ".pdf":
        return _FileResponse(path=str(file_path), media_type="application/pdf")

    # Convert to PDF using LibreOffice (cached)
    cache_dir = _Path("data/preview_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_pdf = cache_dir / f"{doc_id}.pdf"

    # Use cached version if source file hasn't changed and cache is valid
    if cache_pdf.exists() and cache_pdf.stat().st_size > 0 and cache_pdf.stat().st_mtime >= file_path.stat().st_mtime:
        return _FileResponse(path=str(cache_pdf), media_type="application/pdf")

    # Convert with LibreOffice — run in threadpool to avoid blocking async loop
    import subprocess, os
    from starlette.concurrency import run_in_threadpool

    _lo_profile = _Path("/tmp/lo_profile_aminra")
    _lo_profile.mkdir(parents=True, exist_ok=True)

    def _do_convert():
        abs_cache = str(cache_dir.resolve())
        abs_file = str(file_path.resolve())
        # Use unique profile per PID to avoid lock between workers
        pid_profile = f"/tmp/lo_profile_{os.getpid()}"
        os.makedirs(pid_profile, exist_ok=True)
        result = subprocess.run(
            ["/usr/bin/libreoffice", "--headless", "--norestore", "--nolockcheck",
             f"-env:UserInstallation=file://{pid_profile}",
             "--convert-to", "pdf",
             "--outdir", abs_cache, abs_file],
            capture_output=True, timeout=60,
            cwd="/tmp",
            env={"HOME": pid_profile, "PATH": "/usr/bin:/usr/local/bin:/bin",
                 "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        # Find and rename output
        stem = _Path(abs_file).stem
        lo_output = _Path(abs_cache) / (stem + ".pdf")
        resolved_cache = cache_pdf.resolve()
        if lo_output.exists():
            lo_output.rename(resolved_cache)
        elif result.returncode != 0:
            raise RuntimeError(result.stderr.decode()[:200])

    try:
        await run_in_threadpool(_do_convert)
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Chuyển đổi PDF quá thời gian")
    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"[preview] LibreOffice conversion failed: {e}")
        raise HTTPException(500, f"Không thể chuyển đổi sang PDF: {e}")

    if not cache_pdf.exists():
        log.warning(f"[preview] cache_pdf not found: {cache_pdf}")
        raise HTTPException(500, "Chuyển đổi PDF thất bại")

    return _FileResponse(path=str(cache_pdf), media_type="application/pdf")


@router.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db=Depends(get_db),
):
    """Serve the original uploaded file for viewing."""
    user = _get_user_from_header_or_query(request, token)
    _validate_uuid(doc_id)
    row = None
    if user["role"] == "business":
        row = await db.fetchrow(
            "SELECT file_path, original_filename, mime_type FROM documents WHERE id = $1 AND tenant_id = $2",
            doc_id, user.get("tenant_id"),
        )
    elif user["role"] == "provider":
        row = await db.fetchrow(
            """SELECT d.file_path, d.original_filename, d.mime_type FROM documents d
               WHERE d.id = $1 AND EXISTS (
                   SELECT 1 FROM submissions s
                   WHERE (s.provider_id = $2 OR s.auditor_id = $2)
                   AND (
                       $1 = ANY(s.document_ids)
                       OR d.tenant_id = s.business_tenant
                   )
               )""",
            doc_id, user["sub"],
        )
    if not row:
        raise HTTPException(404, "Tài liệu không tồn tại")

    file_path = _Path(row["file_path"]) if row["file_path"] else None
    if not file_path or not file_path.exists():
        raise HTTPException(404, "File không tồn tại trên hệ thống")

    return _FileResponse(
        path=str(file_path),
        filename=row["original_filename"],
        media_type=row["mime_type"] or "application/octet-stream",
    )


# ── Upload (no evaluation) ────────────────────────────────────────────────────

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Upload a document without AI evaluation. It appears as 'Chưa đánh giá'."""
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")
    await check_permission_db(user, "can_upload")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "Tenant không xác định")

    content = await validate_upload(file)
    file_size = len(content)

    tenant_dir = UPLOAD_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    doc_uuid = str(_uuid4())
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (file.filename or "file")).strip()
    save_path = tenant_dir / f"{doc_uuid}_{safe_name}"
    if not save_path.resolve().is_relative_to(tenant_dir.resolve()):
        raise HTTPException(400, "Invalid file path")
    save_path.write_bytes(content)

    mime = file.content_type or "application/octet-stream"
    row = await db.fetchrow(
        """INSERT INTO documents
              (filename, original_filename, file_path, file_size, mime_type,
               user_id, tenant_id, doc_type)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id, uploaded_at""",
        save_path.name, file.filename, str(save_path),
        file_size, mime, user["sub"], tenant_id, doc_type,
    )
    log.info(f"[documents] Uploaded {file.filename} for tenant {tenant_id} (no eval)")
    return {"id": str(row["id"]), "filename": file.filename, "doc_type": doc_type}


# ── Evaluate existing document ───────────────────────────────────────���────────

async def _run_evaluate_background(doc_id: str, file_path: _Path, original_filename: str, doc_type: str | None, lang: str = "vi"):
    """Run AI evaluation in background — updates DB when done."""
    from auth.db import get_pool
    from pipeline.evaluate import evaluate_document

    _DOC_TYPE_LABELS = {
        "halal_policy": "Halal Policy", "has_manual": "HAS Manual",
        "halal_manual": "Halal Manual", "internal_halal_committee": "Internal Halal Committee",
        "company_profile": "Company Profile", "ingredient_raw_material": "Ingredient & Raw Material",
        "process_flow_chart": "Process Flow Chart",
        "sop_raw_material_receiving": "SOP - Raw Material Receiving",
        "sop_storage_segregation": "SOP - Storage & Segregation",
        "sop_production_operation": "SOP - Production Operation",
        "sop_cleaning_sanitation": "SOP - Cleaning & Sanitation",
        "sop_handling_nonconformances": "SOP - Handling Non-Conformances",
        "sop_complaint_recall": "SOP - Complaint & Recall",
    }

    forced_doc_type = doc_type
    forced_doc_label = _DOC_TYPE_LABELS.get(doc_type or "", "")
    template_criteria = None
    template_files_content = ""
    template_files_dir = None

    templates_dir = _Path(os.getenv("TEMPLATES_DIR", "./admin_templates"))
    template_files_base = templates_dir / "files"

    if forced_doc_type:
        template_json = templates_dir / f"{forced_doc_type}.json"
        if template_json.exists():
            try:
                template_criteria = _json.loads(template_json.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Use lang-specific reference files if available
        lang_dir = template_files_base / forced_doc_type / lang
        root_dir = template_files_base / forced_doc_type
        dt_files_dir = lang_dir if lang_dir.exists() and any(lang_dir.iterdir()) else root_dir
        if dt_files_dir.exists():
            template_files_dir = dt_files_dir
            try:
                from pipeline.evaluate import load_template_files_content
                template_files_content = load_template_files_content(dt_files_dir)
            except Exception:
                pass

    pool = get_pool()
    try:
        from starlette.concurrency import run_in_threadpool
        result = await run_in_threadpool(
            evaluate_document,
            file_path, original_filename,
            forced_doc_type=forced_doc_type,
            forced_doc_label=forced_doc_label,
            template_criteria=template_criteria,
            template_files_dir=template_files_dir,
            template_files_content=template_files_content,
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE documents
                   SET compliance_score = $1, evaluation_result = $2, status = 'uploaded'
                   WHERE id = $3""",
                result.get("compliance_score"),
                _json.dumps(result, ensure_ascii=False),
                doc_id,
            )
        log.info(f"[documents] Evaluated {doc_id}: score={result.get('compliance_score')}")
    except Exception as e:
        log.error(f"[documents] Background evaluate error for {doc_id}: {e}")
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE documents SET status = 'uploaded' WHERE id = $1", doc_id,
                )
        except Exception:
            pass


@router.post("/documents/{doc_id}/evaluate")
async def evaluate_existing_document(
    doc_id: str,
    lang: str = Query("vi"),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Trigger AI evaluation in background. Returns immediately."""
    _validate_uuid(doc_id)
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")
    if lang not in ("vi", "en"):
        lang = "vi"

    tenant_id = user.get("tenant_id")
    row = await db.fetchrow(
        "SELECT file_path, original_filename, doc_type, status FROM documents WHERE id = $1 AND tenant_id = $2",
        doc_id, tenant_id,
    )
    if not row:
        raise HTTPException(404, "Tài liệu không tồn tại")
    if row["status"] == "evaluating":
        return {"status": "evaluating", "message": "Tài liệu đang được đánh giá"}

    file_path = _Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "File không tồn tại trên hệ thống")

    # Mark as evaluating
    await db.execute("UPDATE documents SET status = 'evaluating' WHERE id = $1", doc_id)

    # Launch background task with language
    import asyncio
    asyncio.create_task(
        _run_evaluate_background(doc_id, file_path, row["original_filename"], row["doc_type"], lang)
    )

    return {"status": "evaluating", "message": "Đang đánh giá tài liệu..."}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    _validate_uuid(doc_id)
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")
    await check_permission_db(user, "can_delete")

    tenant_id = user.get("tenant_id")
    row = await db.fetchrow(
        "SELECT id, file_path FROM documents WHERE id = $1 AND tenant_id = $2",
        doc_id, tenant_id,
    )
    if not row:
        raise HTTPException(404, "Tài liệu không tồn tại")

    # Delete physical file if exists
    if row["file_path"]:
        from pathlib import Path
        p = Path(row["file_path"])
        p.unlink(missing_ok=True)

    await db.execute("DELETE FROM documents WHERE id = $1", doc_id)
    log.info(f"[documents] Deleted {doc_id} by {user['sub']}")
    return {"message": "Đã xoá tài liệu"}


# ── Dashboard Stats ───────────────────────────────────────────────────────────

# All 13 Halal document types
_ALL_DOC_TYPES = {
    "halal_policy":                 "Halal Policy",
    "has_manual":                   "HAS Manual",
    "internal_halal_committee":     "Internal Halal Committee",
    "company_profile":              "Company Profile",
    "halal_manual":                 "Halal Manual",
    "ingredient_raw_material":      "Ingredient & Raw Material",
    "process_flow_chart":           "Process Flow Chart",
    "sop_raw_material_receiving":   "SOP - Raw Material Receiving",
    "sop_storage_segregation":      "SOP - Storage & Segregation",
    "sop_production_operation":     "SOP - Production Operation",
    "sop_cleaning_sanitation":      "SOP - Cleaning & Sanitation",
    "sop_handling_nonconformances": "SOP - Handling Non-Conformances",
    "sop_complaint_recall":         "SOP - Complaint & Recall",
}


@router.get("/dashboard/stats")
async def dashboard_stats(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Dashboard stats for business users — compliance progress, recent activity."""
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "Tenant không xác định")

    # 1. Per-doc-type stats (latest document per type)
    type_rows = await db.fetch(
        """
        SELECT DISTINCT ON (doc_type)
               doc_type, compliance_score, evaluation_result, original_filename, uploaded_at
        FROM documents
        WHERE tenant_id = $1 AND doc_type IS NOT NULL
        ORDER BY doc_type, uploaded_at DESC
        """,
        tenant_id,
    )

    doc_type_progress = []
    compliant_count = 0
    total_score = 0
    scored_count = 0

    submitted_types = set()
    for r in type_rows:
        dt = r["doc_type"]
        submitted_types.add(dt)
        er = _parse_result(r["evaluation_result"]) or {}
        status = er.get("overall_status")
        score = r["compliance_score"]
        if score is not None:
            total_score += score
            scored_count += 1
        if status in ("compliant", "cb_approved"):
            compliant_count += 1
        doc_type_progress.append({
            "doc_type": dt,
            "label": _ALL_DOC_TYPES.get(dt, dt),
            "score": score,
            "status": status,
            "filename": r["original_filename"],
            "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
        })

    # Add missing doc types
    for dt, label in _ALL_DOC_TYPES.items():
        if dt not in submitted_types:
            doc_type_progress.append({
                "doc_type": dt,
                "label": label,
                "score": None,
                "status": None,
                "filename": None,
                "uploaded_at": None,
            })

    # Sort: submitted first (by label), then missing (by label)
    doc_type_progress.sort(key=lambda x: (x["score"] is None, x["label"]))

    # 2. Aggregate stats
    total_docs_row = await db.fetchrow(
        "SELECT COUNT(*) FROM documents WHERE tenant_id = $1", tenant_id
    )
    member_count_row = await db.fetchrow(
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false", tenant_id
    )

    total_types = len(_ALL_DOC_TYPES)
    readiness = round((compliant_count / total_types) * 100) if total_types > 0 else 0

    # 3. Recent activity (last 5 documents)
    recent_rows = await db.fetch(
        """
        SELECT d.original_filename, d.doc_type, d.compliance_score,
               d.uploaded_at, d.evaluation_result,
               u.company_name AS uploaded_by
        FROM documents d
        LEFT JOIN users u ON u.id = d.user_id
        WHERE d.tenant_id = $1
        ORDER BY d.uploaded_at DESC
        LIMIT 5
        """,
        tenant_id,
    )

    recent = []
    for r in recent_rows:
        er = _parse_result(r["evaluation_result"]) or {}
        recent.append({
            "filename": r["original_filename"],
            "doc_type": r["doc_type"],
            "doc_type_label": _ALL_DOC_TYPES.get(r["doc_type"] or "", r["doc_type"]),
            "score": r["compliance_score"],
            "status": er.get("overall_status"),
            "uploaded_by": r["uploaded_by"],
            "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
        })

    return {
        "readiness": readiness,
        "compliant_count": compliant_count,
        "total_types": total_types,
        "submitted_count": len(submitted_types),
        "total_documents": total_docs_row["count"],
        "avg_score": round(total_score / scored_count) if scored_count > 0 else None,
        "member_count": member_count_row["count"],
        "doc_type_progress": doc_type_progress,
        "recent_activity": recent,
    }
