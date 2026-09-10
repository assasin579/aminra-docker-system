import os
import sys
import logging
import json as _json
import uuid
import re
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, FileResponse
from pydantic import BaseModel

from starlette.concurrency import run_in_threadpool
from pipeline.query import (
    HalalRAG,
    embed_query,
    hybrid_search,
    build_context,
    build_system_prompt,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    LLM_BASE_URL,
    LLM_MODEL,
)
from pipeline.ingest import ingest_file, ensure_collection, get_qdrant_client
from pipeline.evaluate import evaluate_document
from auth.db import init_pool, close_pool
from auth.router import router as auth_router
from auth.admin_router import router as admin_auth_router
from auth.document_router import router as document_router
from auth.identity import resolve_canonical_user_id
from auth.jwt_utils import get_current_user, decode_token
from auth.rate_limit import rate_limit_api, rate_limit_upload
from auth.upload_utils import validate_upload

from services.observability import setup_observability  # noqa: E402

# Note: structlog is configured inside setup_observability, called below
# after FastAPI app is constructed. Until then, use stdlib root logger.
log = logging.getLogger("aminra.api")

# ── Sentry (optional) ─────────────────────────────────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "production"),
    )
    log.info("Sentry initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.pdf_renderer import PDFRenderer
    from services.pdf_data_aggregator import PDFDataAggregator
    from services.pdf_filter_pipeline import FilterPipeline

    await init_pool()
    # 3-stage pipeline: aggregator (Stage 1) → filter pipeline (Stage 2) → renderer (Stage 3)
    app.state.pdf_aggregator = PDFDataAggregator()
    app.state.pdf_filter_pipeline = FilterPipeline()
    app.state.pdf_renderer = PDFRenderer()
    try:
        await app.state.pdf_renderer.startup()
    except Exception:
        log.exception("[lifespan] PDF renderer startup failed; routes will return 503")
    try:
        yield
    finally:
        try:
            await app.state.pdf_renderer.shutdown()
        except Exception:
            log.exception("[lifespan] PDF renderer shutdown error (ignored)")
        await close_pool()


_is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
app = FastAPI(
    title="Aminra — Halal Certification AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://fe.silvergem.org,https://mukjizat.silvergem.org").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["authorization", "content-type", "x-request-id"],
    allow_credentials=True,
    expose_headers=["x-request-id"],
    max_age=3600,
)

# Observability: structlog + request-id + Prometheus /metrics
setup_observability(app)

from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


from auth.submission_router import router as submission_router
from auth.certificate_router import router as certificate_router
from auth.notification_router import router as notification_router
from auth.audit_router import router as audit_router
from auth.audit_log_router import router as audit_log_router
# Phase 4b (2026-05-14): password_reset_router removed — Keycloak built-in flow
# handles password reset via /realms/aminra/login-actions/reset-credentials
from auth.admin_analytics_router import router as admin_analytics_router
from auth.gdpr_router import router as gdpr_router
from auth.feature_flags_router import router as feature_flags_router, admin_router as feature_flags_admin_router
from auth.industry_schema_router import router as industry_schema_router, admin_router as industry_schema_admin_router
from auth.standard_type_router import router as standard_type_router, admin_router as standard_type_admin_router
from auth.dossier_router import router as dossier_router
from auth.pdf_render_router import router as pdf_render_router

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_auth_router, prefix="/auth", tags=["auth-admin"])
app.include_router(audit_log_router, prefix="/auth", tags=["audit-logs"])
app.include_router(admin_analytics_router, prefix="/auth", tags=["admin-analytics"])
app.include_router(feature_flags_admin_router, prefix="/auth/admin", tags=["admin-feature-flags"])
app.include_router(industry_schema_admin_router, prefix="/auth/admin/industry-schemas", tags=["admin-industry-schemas"])
app.include_router(gdpr_router, prefix="/api/users", tags=["data-rights"])
app.include_router(feature_flags_router, prefix="/api/feature-flags", tags=["feature-flags"])
app.include_router(industry_schema_router, prefix="/industry-schemas", tags=["industry-schemas"])
app.include_router(standard_type_router, prefix="/standard-types", tags=["standard-types"])
app.include_router(standard_type_admin_router, prefix="/auth/admin/standard-types", tags=["admin-standard-types"])
app.include_router(dossier_router, prefix="/dossiers", tags=["dossiers"])
app.include_router(pdf_render_router, prefix="/api/templates", tags=["pdf-render"])
app.include_router(document_router, prefix="/api", tags=["documents"])
app.include_router(submission_router, prefix="/api/submissions", tags=["submissions"])
app.include_router(certificate_router, prefix="/api/submissions", tags=["certificates"])
app.include_router(notification_router, prefix="/api/notifications", tags=["notifications"])
app.include_router(audit_router, prefix="/api/audits", tags=["audits"])

from supply_chain.supplier_router import router as supplier_router
from supply_chain.material_router import router as material_router
from supply_chain.process_router import router as process_router
from supply_chain.batch_router import router as batch_router

app.include_router(supplier_router, prefix="/api/supply-chain", tags=["supply-chain"])
app.include_router(material_router, prefix="/api/supply-chain", tags=["supply-chain"])
app.include_router(process_router, prefix="/api/supply-chain", tags=["supply-chain"])
app.include_router(batch_router, prefix="/api/supply-chain", tags=["supply-chain"])

rag = HalalRAG()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./docs"))
REVIEWS_DIR = Path(os.getenv("REVIEWS_DIR", "./reviews"))
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", "./admin_templates"))
TEMPLATE_FILES_DIR = TEMPLATES_DIR / "files"
TEMPLATE_REVISIONS_DIR = TEMPLATES_DIR / "revisions"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_FILES_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_REVISIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Admin auth (Phase 4c: Keycloak realm role `platform_admin`) ────────────────
# Legacy opaque-session admin (/admin/login + admin_sessions.json file) removed
# 2026-05-14 — admin now authenticates via standard Keycloak SSO flow, then
# `_require_admin` checks JWT for realm role `platform_admin`.


def _require_admin(request: Request):
    """Validate Keycloak JWT + check realm role `platform_admin`.

    Returns claims dict on success (caller can ignore). Raises 401/403 otherwise.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = auth[7:]
    claims = decode_token(token)
    realm_roles = (claims.get("realm_access") or {}).get("roles", [])
    if "platform_admin" not in realm_roles:
        raise HTTPException(403, "Admin access required (Keycloak realm role `platform_admin`)")
    return claims


# ── Halal document type registry ───────────────────────────────────────────────
HALAL_DOC_TYPES: Dict[str, str] = {
    "halal_policy": "Halal Policy",
    "has_manual": "HAS Manual",
    "internal_halal_committee": "Internal Halal Committee",
    "company_profile": "Company Profile",
    "halal_manual": "Halal Manual",
    "ingredient_raw_material": "Ingredient & Raw Material Documentation",
    "process_flow_chart": "Process Flow Chart",
    "sop_raw_material_receiving": "SOP - Raw Material Receiving",
    "sop_storage_segregation": "SOP - Storage and Segregation",
    "sop_production_operation": "SOP - Production or Service Operation",
    "sop_cleaning_sanitation": "SOP - Cleaning and Sanitation",
    "sop_handling_nonconformances": "SOP - Handling Non-Conformances",
    "sop_complaint_recall": "SOP - Complaint and Recall Management",
}

# ── Template caches ────────────────────────────────────────────────────────────
_template_json_cache: Dict[str, tuple] = {}
_template_files_cache: Dict[str, tuple] = {}


def _dir_mtime_sum(d: Path) -> float:
    if not d.exists():
        return 0.0
    return sum(f.stat().st_mtime for f in d.iterdir() if f.is_file())


def _append_revision(doc_type: str, entry: dict):
    rev_file = TEMPLATE_REVISIONS_DIR / f"{doc_type}.json"
    revisions: list = []
    if rev_file.exists():
        try:
            revisions = _json.loads(rev_file.read_text())
        except Exception:
            revisions = []
    revisions.append(entry)
    rev_file.write_text(_json.dumps(revisions, ensure_ascii=False, indent=2))


def _load_template(doc_type: str) -> Optional[Dict]:
    p = TEMPLATES_DIR / f"{doc_type}.json"
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    cached = _template_json_cache.get(doc_type)
    if cached and cached[1] == mtime:
        return cached[0]
    data = _json.loads(p.read_text(encoding="utf-8"))
    _template_json_cache[doc_type] = (data, mtime)
    return data


def _load_template_files_content(doc_type: str, lang: str = "vi") -> str:
    from pipeline.evaluate import load_template_files_content

    # W1-M1 — Strict lang-specific dir only. The previous fallback to root_dir
    # mixed languages (e.g. an English-only halal_policy template surfaced for
    # vi requests because root contained only EN files), polluting the LLM
    # context. If lang_dir is empty/missing, return empty content rather than
    # leaking another lang's reference material.
    lang_dir = TEMPLATE_FILES_DIR / doc_type / lang
    if not (lang_dir.exists() and any(lang_dir.iterdir())):
        return ""

    cache_key = f"{doc_type}_{lang}"
    mtime_sum = _dir_mtime_sum(lang_dir)
    cached = _template_files_cache.get(cache_key)
    if cached and cached[1] == mtime_sum:
        return cached[0]
    content = load_template_files_content(lang_dir)
    _template_files_cache[cache_key] = (content, mtime_sum)
    log.info(f"[cache] Template files re-extracted for {cache_key} ({len(content)} chars)")
    return content


TOPIC_LIST = [
    "audit_principles",
    "audit_planning",
    "audit_types",
    "audit_team",
    "halal_standard",
    "non_conformance",
    "documentation",
    "fiqh_halal",
    "certification_body",
    "logistics",
]


class ChatRequest(BaseModel):
    question: str
    top_k: int = 6
    topic_filter: Optional[str] = None
    agent_id: Optional[str] = "aminra"
    lang: Optional[str] = None
    history: List[Dict[str, Any]] = []


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list
    scores: list
    chunks_used: int


class IngestStatus(BaseModel):
    filename: str
    chunks: int
    status: str
    job_id: str | None = None


class EvalIssue(BaseModel):
    section: str
    severity: str
    issue: str
    recommendation: str
    reference: str


class GapAnalysis(BaseModel):
    critical_gaps: List[str] = []
    major_gaps: List[str] = []
    minor_gaps: List[str] = []


class RiskFlag(BaseModel):
    text_snippet: str
    risk_type: str
    severity: str
    explanation: str


class Citation(BaseModel):
    standard: str
    clause: str
    text: str
    relevance: str


class EvaluationReport(BaseModel):
    filename: str
    doc_type: str
    doc_type_label: str
    word_count: int
    standards_found: int
    compliance_score: int
    overall_status: str
    summary: str
    issues: list
    strengths: list
    recommendations: list
    standards_checked: list
    gap_analysis: Optional[Dict] = None
    risk_flags: List[Dict] = []
    citations: List[Dict] = []
    extracted_text: Optional[str] = None


class RewriteRequest(BaseModel):
    section_text: str
    issue: str
    doc_type: str = "general"


class RewriteResponse(BaseModel):
    original: str
    rewritten: str
    explanation: str
    standards_referenced: List[str] = []


class AuditorReview(BaseModel):
    filename: str
    reviewer: str
    notes: str = ""
    confirmed_issues: List[str] = []
    false_positives: List[str] = []
    additional_findings: List[str] = []
    status: str = "pending"
    reviewed_at: str = ""


class TemplateCriterion(BaseModel):
    id: str
    name: str
    description: str
    weight: int = 10


class DocxMetaItem(BaseModel):
    key: str = ""
    value: str = ""


class DocxCustomSection(BaseModel):
    title: str = ""
    content: str = ""  # plain text, one paragraph per line


class DocxConfig(BaseModel):
    # Cover page
    cover_meta: List[DocxMetaItem] = []
    confidential_label: str = "TÀI LIỆU NỘI BỘ"
    # Structural sections
    show_toc: bool = False
    show_revision_table: bool = True
    show_approval_block: bool = True
    # Custom sections before main content
    custom_sections: List[DocxCustomSection] = []


class TemplateConfig(BaseModel):
    doc_type: str
    label: str = ""
    mandatory_criteria: List[TemplateCriterion] = []
    evaluation_guidance: str = ""
    docx_config: Optional[DocxConfig] = None
    updated_at: str = ""


# ── Admin endpoints ────────────────────────────────────────────────────────────


@app.get("/admin/verify")
def admin_verify(request: Request):
    try:
        _require_admin(request)
        return {"valid": True}
    except HTTPException:
        return {"valid": False}


@app.get("/admin/doc-types")
def list_doc_types(request: Request):
    _require_admin(request)
    return {"doc_types": [{"id": k, "label": v} for k, v in HALAL_DOC_TYPES.items()]}


@app.get("/admin/templates")
def list_templates(request: Request):
    _require_admin(request)
    result = []
    for dt_id, dt_label in HALAL_DOC_TYPES.items():
        p = TEMPLATES_DIR / f"{dt_id}.json"
        if p.exists():
            result.append(_json.loads(p.read_text(encoding="utf-8")))
        else:
            result.append(
                {
                    "doc_type": dt_id,
                    "label": dt_label,
                    "mandatory_criteria": [],
                    "evaluation_guidance": "",
                    "updated_at": "",
                }
            )
    return {"templates": result}


@app.get("/admin/templates/{doc_type}")
def get_template(doc_type: str, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    p = TEMPLATES_DIR / f"{doc_type}.json"
    if p.exists():
        return _json.loads(p.read_text(encoding="utf-8"))
    return {
        "doc_type": doc_type,
        "label": HALAL_DOC_TYPES[doc_type],
        "mandatory_criteria": [],
        "evaluation_guidance": "",
        "updated_at": "",
    }


@app.put("/admin/templates/{doc_type}")
def save_template(doc_type: str, config: TemplateConfig, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    config.doc_type = doc_type
    config.label = HALAL_DOC_TYPES[doc_type]
    config.updated_at = datetime.utcnow().isoformat()
    p = TEMPLATES_DIR / f"{doc_type}.json"
    p.write_text(_json.dumps(config.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"message": "Template saved", "doc_type": doc_type}


@app.get("/admin/templates/{doc_type}/files")
def list_template_files(doc_type: str, request: Request, lang: str = ""):
    """List reference files. If lang specified (vi/en), list from lang subfolder."""
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang and lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ")

    # If lang specified, list from subfolder; otherwise list all
    if lang:
        dir_path = TEMPLATE_FILES_DIR / doc_type / lang
    else:
        # Return both vi and en
        result: Dict[str, list] = {"vi": [], "en": []}
        for l in ("vi", "en"):
            d = TEMPLATE_FILES_DIR / doc_type / l
            if d.exists():
                result[l] = [
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
                    }
                    for f in sorted(d.iterdir())
                    if f.is_file()
                ]
        # Also include legacy root files (not in vi/en subfolder)
        root = TEMPLATE_FILES_DIR / doc_type
        if root.exists():
            legacy = [
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
                }
                for f in sorted(root.iterdir())
                if f.is_file() and not f.name.endswith(("_vi.docx", "_en.docx"))
            ]
            if legacy:
                result["legacy"] = legacy
        return {"files_by_lang": result}

    if not dir_path.exists():
        return {"files": []}
    files = [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
        }
        for f in sorted(dir_path.iterdir())
        if f.is_file()
    ]
    return {"files": files}


@app.post("/admin/templates/{doc_type}/files")
async def upload_template_file(doc_type: str, request: Request, file: UploadFile = File(...), lang: str = Form("vi")):
    """Upload reference file to a language subfolder."""
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ (vi hoặc en)")
    content = await validate_upload(file)
    dir_path = TEMPLATE_FILES_DIR / doc_type / lang
    dir_path.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in file.filename).strip()
    save_path = dir_path / safe_name
    if not save_path.resolve().is_relative_to(dir_path.resolve()):
        raise HTTPException(400, "Invalid file path")
    save_path.write_bytes(content)
    _template_files_cache.pop(f"{doc_type}_{lang}", None)
    log.info(f"[admin] Ref file uploaded: {doc_type}/{lang}/{safe_name}")
    return {"message": "File uploaded", "filename": safe_name, "lang": lang}


@app.delete("/admin/templates/{doc_type}/files/{filename}")
def delete_template_file(doc_type: str, filename: str, request: Request, lang: str = "vi"):
    """Delete reference file from a language subfolder."""
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ")
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename).strip()
    base_dir = TEMPLATE_FILES_DIR / doc_type / lang
    file_path = base_dir / safe_name
    if not file_path.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(400, "Invalid file path")
    if not file_path.exists():
        raise HTTPException(404, "File không tồn tại")
    file_path.unlink()
    _template_files_cache.pop(f"{doc_type}_{lang}", None)
    log.info(f"[admin] Ref file deleted: {doc_type}/{lang}/{safe_name}")
    return {"message": "File deleted", "filename": safe_name}


@app.get("/admin/templates/{doc_type}/revisions")
def get_template_revisions(doc_type: str, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    rev_file = TEMPLATE_REVISIONS_DIR / f"{doc_type}.json"
    if not rev_file.exists():
        return {"revisions": []}
    try:
        revisions = _json.loads(rev_file.read_text())
        return {"revisions": list(reversed(revisions))}
    except Exception:
        return {"revisions": []}


@app.post("/admin/templates/{doc_type}/template-file")
async def upload_template_file_lang(
    doc_type: str,
    request: Request,
    file: UploadFile = File(...),
    lang: str = Form("vi"),
):
    """Upload a DOCX template for a specific language (vi/en)."""
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ (vi hoặc en)")
    content = await validate_upload(file)
    dir_path = TEMPLATE_FILES_DIR / doc_type
    dir_path.mkdir(parents=True, exist_ok=True)
    # Keep original filename for display, but save with convention name
    original_name = file.filename or "template.docx"
    save_name = f"{doc_type}_{lang}.docx"
    save_path = dir_path / save_name
    save_path.write_bytes(content)
    _template_files_cache.pop(doc_type, None)
    log.info(f"[admin] Template {lang.upper()} uploaded: {doc_type}/{save_name}")
    return {"message": f"Template {lang.upper()} uploaded", "filename": save_name, "original_filename": original_name}


@app.delete("/admin/templates/{doc_type}/template-file")
def delete_template_file_lang(doc_type: str, request: Request, lang: str = "vi"):
    """Delete a language-specific DOCX template."""
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404)
    if lang not in ("vi", "en"):
        raise HTTPException(400)
    save_path = TEMPLATE_FILES_DIR / doc_type / f"{doc_type}_{lang}.docx"
    if not save_path.exists():
        raise HTTPException(404, f"Template {lang.upper()} chưa được upload")
    save_path.unlink()
    _template_files_cache.pop(doc_type, None)
    return {"message": f"Template {lang.upper()} deleted"}


@app.get("/admin/templates/{doc_type}/template-files")
def list_template_files_lang(doc_type: str, request: Request):
    """List language-specific templates for a doc_type."""
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404)
    result = {}
    for lang in ("vi", "en"):
        f = TEMPLATE_FILES_DIR / doc_type / f"{doc_type}_{lang}.docx"
        if f.exists():
            result[lang] = {
                "filename": f.name,
                "size": f.stat().st_size,
                "updated_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
            }
    return {"templates": result}


# ── Admin file preview endpoints ──────────────────────────────────────────────


def _verify_admin_token_string(token: str) -> bool:
    """Validate a Keycloak JWT passed via `?token=` query string + check
    `platform_admin` realm role.

    Used for file preview links opened in new browser tabs where setting a
    Bearer header isn't possible. Post-Phase-4c the legacy opaque admin
    session is gone — only Keycloak tokens are accepted.
    """
    if not token:
        return False
    try:
        claims = decode_token(token)
    except HTTPException:
        return False
    realm_roles = (claims.get("realm_access") or {}).get("roles", [])
    return "platform_admin" in realm_roles


def _require_admin_or_token(request: Request, token: Optional[str]):
    """Accept either a `Bearer` admin session OR `?token=` query string."""
    if token and _verify_admin_token_string(token):
        return
    _require_admin(request)


def _guess_media_type(filename: str) -> str:
    """Map common extensions to media types so browsers preview when possible."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "md": "text/plain; charset=utf-8",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(ext, "application/octet-stream")


# Office formats browsers cannot render natively — convert to PDF for inline view.
_OFFICE_CONVERT_EXTS = {"docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt"}
import tempfile as _tempfile

_PDF_PREVIEW_CACHE_DIR = Path(_tempfile.gettempdir()) / "aminra_pdf_preview"


def _convert_office_to_pdf_cached(src: Path) -> Optional[Path]:
    """Convert an Office doc to PDF for in-browser preview.

    Cache key = source path hash + mtime. Re-converts only when source is newer
    than cached PDF. Uses LibreOffice headless (~3 sec for typical DOCX).
    Returns None on conversion failure (caller falls back to original file).
    """
    import hashlib
    import subprocess

    if not src.exists():
        return None
    cache_key = hashlib.sha1(f"{src}|{src.stat().st_mtime}".encode(), usedforsecurity=False).hexdigest()[:16]
    _PDF_PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = _PDF_PREVIEW_CACHE_DIR / f"{cache_key}.pdf"
    if cached.exists() and cached.stat().st_mtime >= src.stat().st_mtime:
        return cached
    try:
        # Isolated tmpdir per conversion: two files with the same stem (e.g.
        # halal_policy_vi.docx in different subdirs) would otherwise produce
        # the same intermediate filename in the shared outdir, causing the
        # second conversion to overwrite the first's output.
        with _tempfile.TemporaryDirectory(dir=_PDF_PREVIEW_CACHE_DIR) as tmpdir:
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, str(src)],
                capture_output=True,
                timeout=60,
            )
            if result.returncode != 0:
                log.warning(f"[pdf_preview] libreoffice failed for {src}: {result.stderr.decode(errors='ignore')[:200]}")
                return None
            produced = Path(tmpdir) / f"{src.stem}.pdf"
            if not produced.exists():
                return None
            produced.rename(cached)
        return cached
    except subprocess.TimeoutExpired:
        log.warning(f"[pdf_preview] timeout converting {src}")
        return None
    except FileNotFoundError:
        log.warning("[pdf_preview] libreoffice not installed — skipping conversion")
        return None
    except Exception as e:
        log.warning(f"[pdf_preview] unexpected error: {e}")
        return None


def _maybe_serve_as_pdf(file: Path) -> tuple[Path, str]:
    """If `file` is an Office doc, return (pdf_path, 'application/pdf').
    Otherwise return (file, original_media_type). PDF preview supersedes
    download for any browser-renderable preview.
    """
    ext = file.suffix.lstrip(".").lower()
    if ext in _OFFICE_CONVERT_EXTS:
        pdf = _convert_office_to_pdf_cached(file)
        if pdf:
            return pdf, "application/pdf"
    return file, _guess_media_type(file.name)


@app.get("/admin/templates/{doc_type}/template-file/view")
def view_template_file(doc_type: str, request: Request, lang: str = "vi", token: Optional[str] = None):
    """Serve the canonical {doc_type}_{lang}.docx for admin preview/verification."""
    _require_admin_or_token(request, token)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ")
    f = TEMPLATE_FILES_DIR / doc_type / f"{doc_type}_{lang}.docx"
    if not f.exists():
        raise HTTPException(404, f"Template {lang.upper()} chưa được upload")
    served, media = _maybe_serve_as_pdf(f)
    display_name = served.name if served != f else f.name
    return FileResponse(
        path=str(served),
        media_type=media,
        filename=display_name,
        headers={"Content-Disposition": f'inline; filename="{display_name}"'},
    )


@app.get("/admin/templates/{doc_type}/files/{filename}/view")
def view_reference_file(doc_type: str, filename: str, request: Request, lang: str = "vi", token: Optional[str] = None):
    """Serve a reference file from the lang subfolder for admin preview."""
    _require_admin_or_token(request, token)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ")
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename).strip()
    base_dir = TEMPLATE_FILES_DIR / doc_type / lang
    f = base_dir / safe_name
    if not f.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(400, "Invalid file path")
    if not f.exists() or not f.is_file():
        raise HTTPException(404, "File không tồn tại")
    served, media = _maybe_serve_as_pdf(f)
    display_name = served.name if served != f else f.name
    return FileResponse(
        path=str(served),
        media_type=media,
        filename=display_name,
        headers={"Content-Disposition": f'inline; filename="{display_name}"'},
    )


# ── Public template endpoints (for document creation) ─────────────────────────


def _find_template_file(doc_type: str, lang: str) -> Optional[Path]:
    """Find template DOCX for a doc_type + language (vi/en).

    Strict match on `{doc_type}_{lang}.docx` to prevent cross-contamination
    when the directory contains stray files (e.g., manual uploads with custom
    filenames). Only the canonical filename is served to end users.
    """
    canonical = TEMPLATE_FILES_DIR / doc_type / f"{doc_type}_{lang}.docx"
    return canonical if canonical.exists() else None


@app.get("/templates/available")
def list_available_templates():
    """List doc_types với format availability (DOCX và/hoặc PDF).

    Trả về tất cả doc_types trong HALAL_DOC_TYPES, mỗi item có:
      - has_vi / has_en — file DOCX upload (admin_templates/files/)
      - has_pdf — PDF template render via Playwright (templates_html/)
      - format_available: 'docx' | 'pdf' | 'both' | 'none'

    Mục đích: user thấy hết 13 doc_types kể cả khi admin chưa upload DOCX
    (vẫn có thể generate qua PDF render). FE display badge theo
    format_available để user chọn đúng mode.
    """
    # Pre-load PDF registry để check pdf availability
    try:
        from templates_html._registry import list_supported as _pdf_supported
        _pdf_doc_types = {
            i["doc_type"]: i.get("implemented", False) for i in _pdf_supported()
        }
    except Exception:
        _pdf_doc_types = {}

    # Merge sources: HALAL_DOC_TYPES (DOCX legacy) + PDF registry (HTML).
    # Skip internal-only entries (_style_guide) and aliases (halal_manual is
    # alias of has_manual — show one canonical entry only).
    merged_doc_types: dict[str, str] = dict(HALAL_DOC_TYPES)
    for dt, implemented in _pdf_doc_types.items():
        if not implemented:
            continue
        if dt.startswith("_"):  # internal/_style_guide
            continue
        if dt == "halal_manual":  # alias of has_manual — skip duplicate
            continue
        if dt not in merged_doc_types:
            # Add doc_type that exists only in PDF registry (vd `generic`)
            merged_doc_types[dt] = dt.replace("_", " ").title()

    # Remove halal_manual alias from output even if in HALAL_DOC_TYPES
    merged_doc_types.pop("halal_manual", None)

    result = []
    for doc_type, label in merged_doc_types.items():
        vi_file = None
        en_file = None
        dir_path = TEMPLATE_FILES_DIR / doc_type
        if dir_path.exists():
            vi_file = _find_template_file(doc_type, "vi")
            en_file = _find_template_file(doc_type, "en")

        has_docx = vi_file is not None or en_file is not None
        has_pdf = bool(_pdf_doc_types.get(doc_type, False))

        if has_docx and has_pdf:
            fmt = "both"
        elif has_docx:
            fmt = "docx"
        elif has_pdf:
            fmt = "pdf"
        else:
            # Neither DOCX nor PDF available — skip (no way to generate)
            continue

        result.append(
            {
                "doc_type": doc_type,
                "label": label,
                "has_vi": vi_file is not None,
                "has_en": en_file is not None,
                "has_pdf": has_pdf,
                "format_available": fmt,
                "vi_size": vi_file.stat().st_size if vi_file else None,
                "en_size": en_file.stat().st_size if en_file else None,
            }
        )
    return {"templates": result}


@app.get("/templates/{doc_type}/download")
def download_template(
    doc_type: str,
    lang: str = "vi",
    _: dict = Depends(get_current_user),
):
    """Download template DOCX for a specific language.

    Cache-Control no-store: admin may rotate template content; serving stale
    cached copies (browser HTTP cache OR PWA service worker) is what caused
    the 2026-04-26 'halal_policy → rửa dọn' incident even after data fix.
    """
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ (vi hoặc en)")
    template = _find_template_file(doc_type, lang)
    if not template:
        raise HTTPException(404, f"Template {lang.upper()} chưa được upload cho {doc_type}")
    # ETag based on file mtime so browsers know when content changes.
    etag = f'"{int(template.stat().st_mtime)}-{template.stat().st_size}"'
    return FileResponse(
        path=str(template),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=template.name,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "ETag": etag,
        },
    )


# ── Placeholder management (admin) ────────────────────────────────────────────


@app.get("/admin/placeholders")
async def list_placeholders(request: Request):
    _require_admin(request)
    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM custom_placeholders ORDER BY is_system DESC, created_at")
    return {"placeholders": [dict(r) | {"id": str(r["id"])} for r in rows]}


@app.post("/admin/placeholders")
async def create_placeholder(request: Request):
    _require_admin(request)
    body = await request.json()
    key = body.get("key", "").strip().lower().replace(" ", "_")
    label = body.get("label", "").strip()
    description = body.get("description", "").strip()
    default_value = body.get("default_value", "").strip()
    source = body.get("source", "").strip()

    if not key or not label:
        raise HTTPException(400, "Key và label là bắt buộc")

    import re

    if not re.match(r"^[a-z][a-z0-9_]*$", key):
        raise HTTPException(400, "Key chỉ chứa chữ thường, số và dấu gạch dưới, bắt đầu bằng chữ")

    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT COUNT(*) FROM custom_placeholders WHERE key=$1", key)
        if existing:
            raise HTTPException(409, f"Placeholder '{key}' đã tồn tại")
        row = await conn.fetchrow(
            "INSERT INTO custom_placeholders (key, label, description, default_value, source) VALUES ($1,$2,$3,$4,$5) RETURNING id",
            key,
            label,
            description or None,
            default_value or None,
            source or None,
        )

    return {"id": str(row["id"]), "key": key, "message": f"Đã tạo placeholder {{{{​{key}}}}}"}


@app.put("/admin/placeholders/{key}")
async def update_placeholder(key: str, request: Request):
    _require_admin(request)
    body = await request.json()
    label = body.get("label", "").strip()
    description = body.get("description", "").strip()
    default_value = body.get("default_value", "").strip()
    source = body.get("source", "").strip()

    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE custom_placeholders
            SET label = COALESCE(NULLIF($1, ''), label),
                description = $2,
                default_value = $3,
                source = $4
            WHERE key = $5 AND is_system = false
        """,
            label,
            description or None,
            default_value or None,
            source or None,
            key,
        )
    if result == "UPDATE 0":
        raise HTTPException(400, "Không thể sửa placeholder hệ thống hoặc không tồn tại")
    return {"message": f"Đã cập nhật placeholder {key}"}


@app.delete("/admin/placeholders/{key}")
async def delete_placeholder(key: str, request: Request):
    _require_admin(request)
    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM custom_placeholders WHERE key=$1 AND is_system=false", key)
    if result == "DELETE 0":
        raise HTTPException(400, "Không thể xoá placeholder hệ thống hoặc không tồn tại")
    return {"message": f"Đã xoá placeholder {key}"}


# ── Public: get all placeholders (for template creation) ─────────────────────


@app.get("/placeholders")
async def get_all_placeholders():
    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, label, description, default_value, source, is_system FROM custom_placeholders ORDER BY is_system DESC, created_at"
        )
    return {"placeholders": [dict(r) for r in rows]}


# ── Admin user management ──────────────────────────────────────────────────────


class AdminCreateUserRequest(BaseModel):
    email: str
    password: str
    company_name: str
    role: str  # 'business' | 'provider'
    company_code: Optional[str] = None
    status: str = "active"


class AdminUpdateUserRequest(BaseModel):
    # Phase 4c-2: profile fields only. Credentials are handled by the dedicated
    # reset route below so profile updates cannot silently ignore credential
    # changes and return false success.
    company_name: Optional[str] = None
    company_code: Optional[str] = None
    status: Optional[str] = None  # active | pending | suspended
    role: Optional[str] = None
    is_owner: Optional[bool] = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str


def _validate_admin_reset_password(new_password: str) -> None:
    if len(new_password) < 10:
        raise HTTPException(400, "Mật khẩu tối thiểu 10 ký tự")
    if not re.search(r"[A-Z]", new_password):
        raise HTTPException(400, "Mật khẩu phải có ít nhất 1 chữ hoa (A-Z)")
    if not re.search(r"[a-z]", new_password):
        raise HTTPException(400, "Mật khẩu phải có ít nhất 1 chữ thường (a-z)")
    if not re.search(r"[0-9]", new_password):
        raise HTTPException(400, "Mật khẩu phải có ít nhất 1 chữ số (0-9)")


@app.get("/admin/users")
async def admin_list_users(
    request: Request,
    role: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
):
    _require_admin(request)
    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        conditions = []
        params: list = []
        idx = 1
        if role:
            conditions.append(f"role = ${idx}")
            params.append(role)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if q:
            conditions.append(f"(email ILIKE ${idx} OR company_name ILIKE ${idx})")
            params.append(f"%{q}%")
            idx += 1
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = await conn.fetch(
            f"""SELECT id, email, role, company_name, company_code,
                       status, is_owner, tenant_id, created_at
                FROM users {where} ORDER BY created_at DESC""",
            *params,
        )
    return {"users": [dict(r) for r in rows], "total": len(rows)}


@app.post("/admin/users")
async def admin_create_user(request: Request, body: AdminCreateUserRequest):
    """Phase 4c-2: admin-created users are provisioned in Keycloak first,
    then mirrored into the local `users` table. Keycloak owns credentials.
    `email_verified=True` because the admin vouches for the identity, so the
    user can log in without an email round-trip."""
    _require_admin(request)
    from auth.db import get_pool
    from auth import keycloak_admin

    # AdminCreateUserRequest.role uses the PG-side taxonomy `business|provider`;
    # Keycloak realm roles split provider into `auditor` vs `cb_admin`. Admin-
    # created provider accounts are CB owners → map to `cb_admin`. Individual
    # auditors come in via /provider/auditors with realm role `auditor`.
    kc_realm_role = "cb_admin" if body.role == "provider" else body.role

    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email=$1", body.email)
        if existing:
            raise HTTPException(400, "Email đã tồn tại")

    try:
        kc_user_id = keycloak_admin.create_user(
            email=body.email,
            password=body.password,
            role=kc_realm_role,
            tenant_id=None,  # owner → tenant_id = own users.id, set below after insert
            is_owner=True,
            user_status=body.status,
            company_name=body.company_name,
            email_verified=True,
        )
    except keycloak_admin.KeycloakAdminError as e:
        if "409" in str(e.detail) or "exists" in str(e.detail).lower():
            raise HTTPException(409, "Email đã được đăng ký trong Keycloak")
        raise

    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """INSERT INTO users
                   (email, keycloak_sub, role, company_name,
                    company_code, status, is_owner, tenant_id)
                   VALUES ($1,$2,$3::user_role,$4,$5,$6::user_status,$7,NULL)
                   RETURNING id,email,role,company_name,company_code,status,is_owner,tenant_id,created_at""",
                body.email,
                kc_user_id,
                body.role,
                body.company_name,
                body.company_code,
                body.status,
                True,
            )
            # Owner accounts are their own tenant root — applies to business
            # owners (DN) and provider owners (CB), both stored with role in
            # ('business', 'provider') in PG.
            if body.role in ("business", "provider"):
                await conn.execute(
                    "UPDATE users SET tenant_id = id WHERE id = $1", row["id"]
                )
                row = await conn.fetchrow(
                    "SELECT id,email,role,company_name,company_code,status,is_owner,tenant_id,created_at "
                    "FROM users WHERE id=$1",
                    row["id"],
                )
        except Exception:
            # Compensate Keycloak side so we don't leak orphan KC users
            try:
                keycloak_admin.delete_user(kc_user_id)
            except Exception:
                log.exception("Compensating delete_user failed for kc_sub=%s", kc_user_id)
            raise
    return dict(row)


@app.post("/admin/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: str,
    request: Request,
    body: AdminResetPasswordRequest,
):
    """Reset a user's Keycloak password from the AMINRA admin UI.

    Keycloak owns credentials; this endpoint is intentionally separate from
    profile PUT so admins cannot get a false-success response when changing a
    credential. The local DB is used only to resolve the linked Keycloak user.
    """
    admin_claims = _require_admin(request)
    _validate_admin_reset_password(body.new_password)
    from auth.db import get_pool
    from auth import keycloak_admin

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT keycloak_sub, email FROM users WHERE id=$1",
            user_id,
        )
    if not row:
        raise HTTPException(404, "User không tồn tại")

    kc_sub = row["keycloak_sub"]
    if not kc_sub and row["email"]:
        kc_sub = keycloak_admin.find_user_by_email(row["email"])
    if not kc_sub:
        raise HTTPException(409, "User chưa được liên kết với Keycloak")

    admin_sub = str(admin_claims.get("sub") or "")
    admin_email = str(admin_claims.get("email") or "").lower()
    target_email = str(row["email"] or "").lower()
    self_reset = bool(
        (admin_sub and admin_sub == str(kc_sub))
        or (admin_email and target_email and admin_email == target_email)
    )

    keycloak_admin.reset_user_password(str(kc_sub), body.new_password)
    return {
        "message": "Đã đổi mật khẩu user",
        "sessions_revoked": True,
        "self_reset": self_reset,
    }


@app.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, request: Request, body: AdminUpdateUserRequest):
    """Phase 4c-2: PG-side profile updates only. Password changes route through
    Keycloak (admin console or future reset-password proxy). Role/realm-role
    sync to Keycloak is deferred to the RBAC engine work (U4 / ADR-006)."""
    _require_admin(request)
    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(404, "User không tồn tại")
        updates: list[str] = []
        params: list = []
        idx = 1
        for field, val in [
            ("company_name", body.company_name),
            ("company_code", body.company_code),
            ("status", body.status),
            ("role", body.role),
            ("is_owner", body.is_owner),
        ]:
            if val is not None:
                updates.append(f"{field} = ${idx}")
                params.append(val)
                idx += 1
        if not updates:
            return dict(row)
        params.append(user_id)
        await conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}", *params)
        row = await conn.fetchrow(
            "SELECT id,email,role,company_name,company_code,status,is_owner,tenant_id,created_at FROM users WHERE id=$1",
            user_id,
        )
    return dict(row)


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    """Phase 4c-2: delete the Keycloak user first (best-effort), then the PG
    row. Best-effort because a KC-side 404 is a no-op (already gone) — we
    don't want a stale KC failure to block a perfectly valid PG cleanup."""
    _require_admin(request)
    if user_id == "54182089-3a6d-458a-994d-93ac4e0c504f":  # guard: never delete seeded admin
        raise HTTPException(403, "Không thể xoá tài khoản admin gốc")
    from auth.db import get_pool
    from auth import keycloak_admin

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, role, tenant_id, email, keycloak_sub FROM users WHERE id=$1",
            user_id,
        )
        if not row:
            raise HTTPException(404, "User không tồn tại")

        kc_sub = row["keycloak_sub"]
        # Fall back to email lookup for users created before keycloak_sub backfill
        if not kc_sub and row["email"]:
            try:
                kc_sub = keycloak_admin.find_user_by_email(row["email"])
            except keycloak_admin.KeycloakAdminError:
                kc_sub = None
        if kc_sub:
            try:
                keycloak_admin.delete_user(str(kc_sub))
            except keycloak_admin.KeycloakAdminError as e:
                log.warning(
                    "Keycloak delete_user failed for %s (sub=%s): %s — continuing PG cleanup",
                    row["email"], kc_sub, e.detail,
                )

        # Delete tenant members first (cascade doesn't cover cross-tenant)
        if row["role"] == "business" and row["tenant_id"] == user_id:
            await conn.execute("DELETE FROM documents WHERE tenant_id=$1", user_id)
            await conn.execute("DELETE FROM users WHERE tenant_id=$1 AND id != $1", user_id, user_id)
        await conn.execute("DELETE FROM users WHERE id=$1", user_id)
    return {"message": "Đã xoá user", "id": user_id}


@app.get("/health")
async def health():
    checks = {"status": "ok", "service": "Aminra Halal Certification AI"}
    # Quick DB check
    try:
        from auth.db import get_pool

        pool = get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["database"] = "connected"
    except Exception:
        checks["database"] = "disconnected"
    # Quick Qdrant check
    try:
        client = get_qdrant_client()
        from pipeline.ingest import COLLECTION_NAME

        client.get_collection(COLLECTION_NAME)
        checks["qdrant"] = "connected"
    except Exception:
        checks["qdrant"] = "disconnected"
    return checks


@app.get("/stats")
def stats():
    try:
        client = get_qdrant_client()
        from pipeline.ingest import COLLECTION_NAME

        info = client.get_collection(COLLECTION_NAME)
        count = client.count(COLLECTION_NAME).count
        return {"collection": COLLECTION_NAME, "vectors": count, "status": str(info.status)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/topics")
def list_topics():
    return {"topics": TOPIC_LIST}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _: None = Depends(rate_limit_api)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question khong duoc de trong")
    if len(req.question) > 1000:
        raise HTTPException(status_code=400, detail="question qua dai (max 1000 ky tu)")
    try:
        result = rag.ask(question=req.question, top_k=req.top_k, topic_filter=req.topic_filter, lang=req.lang)
    except Exception as e:
        log.error(f"RAG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return ChatResponse(
        question=result.question,
        answer=result.answer,
        sources=[],
        scores=result.scores,
        chunks_used=result.chunks_used,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, _: None = Depends(rate_limit_api)):
    if not req.question.strip():
        raise HTTPException(400, "question khong duoc de trong")

    # RAG search (sync ML calls → thread pool)
    query_data = await run_in_threadpool(embed_query, req.question)
    hits = await run_in_threadpool(hybrid_search, query_data, req.top_k, req.topic_filter)
    context = await run_in_threadpool(build_context, hits)

    sys_prompt = build_system_prompt(req.lang)
    prompt = f"{sys_prompt}\n\nCONTEXT:\n{context}\n\nCÂU HỎI: {req.question}"

    api_key = OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = OPENROUTER_BASE_URL if OPENROUTER_API_KEY else LLM_BASE_URL
    model = OPENROUTER_MODEL if OPENROUTER_API_KEY else LLM_MODEL
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if OPENROUTER_API_KEY:
        headers["HTTP-Referer"] = "https://fe.silvergem.org"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
        "stream": True,
    }

    async def generate():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            obj = _json.loads(data)
                            content = (obj.get("choices") or [{}])[0].get("delta", {}).get("content")
                            if content:
                                yield content
                        except (_json.JSONDecodeError, IndexError):
                            continue
        except Exception as e:
            log.error(f"[stream] {e}")
            yield f"\n\n[Lỗi: {e}]"

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/ingest", response_model=IngestStatus)
async def ingest_document(
    file: UploadFile = File(...),
    _: None = Depends(rate_limit_upload),
    user: dict = Depends(get_current_user),  # C12 fix — require auth
):
    """Upload + queue RAG ingest. Returns job_id; poll /jobs/{job_id} for progress."""
    content = await validate_upload(file)

    # C7 fix — sanitize filename + UUID prefix to prevent traversal & cross-tenant overwrites.
    raw_name = file.filename or "doc.bin"
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in raw_name).strip("._") or "doc.bin"
    if len(safe_name) > 100:
        safe_name = safe_name[-100:]
    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex[:12]}_{safe_name}"
    if not save_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(400, "Invalid file path")
    save_path.write_bytes(content)

    from services.jobs import enqueue

    try:
        job = await enqueue("ingest_document", path=str(save_path))
    except Exception as e:
        log.exception("[ingest] enqueue failed")
        raise HTTPException(503, f"Job queue unavailable: {e}")

    return IngestStatus(filename=safe_name, chunks=0, status="queued", job_id=job.job_id)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Poll a background job by ID. Used by clients after /ingest."""
    from services.jobs import get_job_status

    view = await get_job_status(job_id)
    return {
        "job_id": view.job_id,
        "status": view.status,
        "result": view.result,
        "error": view.error,
    }


@app.post("/evaluate", response_model=EvaluationReport)
async def evaluate_doc(
    request: Request,
    file: UploadFile = File(...),
    _rate_limit: None = Depends(rate_limit_upload),
    user: dict = Depends(get_current_user),  # C12 fix — require auth
    doc_type: Optional[str] = Form(None),
    previous_context: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
):
    content = await validate_upload(file)
    suffix = Path(file.filename or "").suffix.lower()
    jwt_user = user  # auth now required, no anonymous fallback

    # C8 fix — sanitize FE-supplied previous_context to neutralize prompt-injection
    # vectors (role markers, system delimiters, oversized payload).
    if previous_context:
        prev = previous_context[:2000]  # hard cap
        # Strip ASCII control chars except whitespace
        prev = "".join(c for c in prev if c == "\n" or c == "\t" or (ord(c) >= 32))
        # Neutralize delimiter markers commonly used in prompt templates
        for marker in ("===", "###", "---SYSTEM", "[SYSTEM]", "<|", "|>", "<<SYS>>"):
            prev = prev.replace(marker, "·" * 3)
        previous_context = prev

    eval_lang = lang or "vi"
    forced_doc_type = doc_type if doc_type and doc_type in HALAL_DOC_TYPES else None
    forced_doc_label = HALAL_DOC_TYPES.get(forced_doc_type, "") if forced_doc_type else ""
    template_criteria = _load_template(forced_doc_type) if forced_doc_type else None
    template_files_content = _load_template_files_content(forced_doc_type, eval_lang) if forced_doc_type else ""
    # W1-M1 fix — strict lang-specific dir; never fall back to root which can
    # contain other-language files (caused halal_policy English content reaching
    # vi evaluation flow in the original incident).
    template_files_dir = None
    if forced_doc_type:
        lang_dir = TEMPLATE_FILES_DIR / forced_doc_type / eval_lang
        if lang_dir.exists():
            template_files_dir = lang_dir
    # If no lang-specific dir → empty content (don't pollute LLM with wrong-lang refs)

    import tempfile
    import uuid as _uuid

    file_bytes = content
    file_size = len(file_bytes)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = evaluate_document(
            tmp_path,
            file.filename,
            forced_doc_type=forced_doc_type,
            forced_doc_label=forced_doc_label,
            template_criteria=template_criteria,
            template_files_dir=template_files_dir,
            template_files_content=template_files_content,
            previous_context=previous_context,
            lang=lang,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log.error(f"Evaluate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    report = EvaluationReport(
        **{
            "filename": result.get("filename", file.filename),
            "doc_type": result.get("doc_type", "general"),
            "doc_type_label": result.get("doc_type_label", "Tài liệu chung"),
            "word_count": result.get("word_count", 0),
            "standards_found": result.get("standards_found", 0),
            "compliance_score": result.get("compliance_score", 0),
            "overall_status": result.get("overall_status", "needs_review"),
            "summary": result.get("summary", ""),
            "issues": result.get("issues", []),
            "strengths": result.get("strengths", []),
            "recommendations": result.get("recommendations", []),
            "standards_checked": result.get("standards_checked", []),
            "gap_analysis": result.get("gap_analysis"),
            "risk_flags": result.get("risk_flags", []),
            "citations": result.get("citations", []),
            "extracted_text": result.get("extracted_text"),
        }
    )

    # Persist to DB if authenticated business user
    if jwt_user and jwt_user.get("role") == "business" and jwt_user.get("tenant_id"):
        try:
            from auth.db import get_pool
            import json as _json_mod

            pool = get_pool()
            async with pool.acquire() as conn:
                # Save file to tenant folder
                tenant_dir = UPLOAD_DIR / jwt_user["tenant_id"]
                tenant_dir.mkdir(parents=True, exist_ok=True)
                doc_uuid = str(_uuid.uuid4())
                safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in file.filename).strip()
                save_path = tenant_dir / f"{doc_uuid}_{safe_name}"
                if not save_path.resolve().is_relative_to(tenant_dir.resolve()):
                    raise HTTPException(400, "Invalid file path")
                save_path.write_bytes(file_bytes)

                mime = file.content_type or "application/octet-stream"
                await conn.execute(
                    """
                    INSERT INTO documents
                        (filename, original_filename, file_path, file_size, mime_type,
                         user_id, tenant_id, doc_type, compliance_score, evaluation_result)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    save_path.name,
                    file.filename,
                    str(save_path),
                    file_size,
                    mime,
                    # documents.user_id is FK → users.id; resolve from JWT.
                    await resolve_canonical_user_id(jwt_user, conn),
                    jwt_user["tenant_id"],
                    result.get("doc_type"),
                    result.get("compliance_score"),
                    _json_mod.dumps(result, ensure_ascii=False),
                )
                log.info(f"[documents] Saved {file.filename} for tenant {jwt_user['tenant_id']}")
        except Exception as e:
            log.error(f"[documents] Failed to save to DB: {e}")
            # Don't fail the evaluate response — just log

    return report


@app.post("/rewrite", response_model=RewriteResponse)
async def suggest_rewrite(
    req: RewriteRequest,
    _rate_limit: None = Depends(rate_limit_upload),  # C13 — share LLM rate limiter
    user: dict = Depends(get_current_user),  # C13 — require auth
):
    if not req.section_text.strip():
        raise HTTPException(status_code=400, detail="section_text không được để trống")

    prompt = f"""Bạn là chuyên gia soạn thảo tài liệu Halal. Hãy viết lại đoạn văn bản sau để đáp ứng tiêu chuẩn Halal.

=== ĐOẠN VĂN GỐC ===
{req.section_text[:1500]}

=== VẤN ĐỀ PHÁT HIỆN ===
{req.issue}

=== LOẠI TÀI LIỆU ===
{req.doc_type}

Hãy viết lại đoạn văn để khắc phục vấn đề trên. Trả về JSON:
{{
  "original": "{req.section_text[:200].replace(chr(10), " ")}...",
  "rewritten": "<đoạn văn đã được viết lại đầy đủ, rõ ràng, đáp ứng Halal>",
  "explanation": "<giải thích ngắn gọn các thay đổi đã thực hiện và lý do>",
  "standards_referenced": ["<tiêu chuẩn JAKIM/HDC áp dụng>"]
}}

Dùng tiếng Việt. Chỉ trả về JSON."""

    raw = None
    try:
        from pipeline.evaluate import call_llm_json, call_deepseek_json

        raw = call_llm_json(prompt)
    except Exception as e:
        log.warning(f"Rewrite OpenRouter failed: {e}")
        try:
            raw = call_deepseek_json(prompt)
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Rewrite LLM failed: {e2}")

    from pipeline.evaluate import parse_json_safe

    result = parse_json_safe(raw)
    return RewriteResponse(
        original=result.get("original", req.section_text[:300]),
        rewritten=result.get("rewritten", ""),
        explanation=result.get("explanation", ""),
        standards_referenced=result.get("standards_referenced", []),
    )


# ─── Generate compliant document (streaming) ─────────────────────────────────


class GenerateDocRequest(BaseModel):
    doc_type: str
    doc_type_label: str
    extracted_text: str = ""
    issues: list = []
    recommendations: list = []
    gap_analysis: Optional[Dict] = None


@app.post("/generate-document")
async def generate_document(
    req: GenerateDocRequest,
    _rate_limit: None = Depends(rate_limit_upload),  # C13 — LLM rate limiter
    user: dict = Depends(get_current_user),  # C13 — require auth
):
    template = _load_template(req.doc_type)
    criteria = template.get("mandatory_criteria", []) if template else []
    ref_ctx = _load_template_files_content(req.doc_type) if req.doc_type else ""

    criteria_str = (
        "\n".join(
            f"{i + 1}. **{c.get('name', '')}** (trọng số {c.get('weight', 10)}pt): {c.get('description', '')}"
            for i, c in enumerate(criteria)
        )
        or "Áp dụng tiêu chuẩn Halal JAKIM/HDC đầy đủ"
    )

    issues_str = (
        "\n".join(
            f"- [{it.get('severity', '').upper()}] {it.get('section', '')}: {it.get('issue', '')} → {it.get('recommendation', '')}"
            for it in req.issues[:20]
        )
        or "Không phát hiện vấn đề cụ thể"
    )

    gaps_str = ""
    if req.gap_analysis:
        cg = req.gap_analysis.get("critical_gaps", [])
        mg = req.gap_analysis.get("major_gaps", [])
        if cg:
            gaps_str += "Critical: " + "; ".join(cg[:5]) + "\n"
        if mg:
            gaps_str += "Major: " + "; ".join(mg[:5])

    original_ctx = req.extracted_text[:10000] if req.extracted_text else ""

    prompt = f"""Bạn là chuyên gia soạn thảo tài liệu chứng nhận Halal.

# NHIỆM VỤ
Cải tiến tài liệu **{req.doc_type_label}** hiện có. Xuất ra tài liệu hoàn chỉnh.

# QUY TẮC — ĐỌC KỸ
Với MỖI đoạn/câu trong tài liệu gốc, hãy quyết định 1 trong 3:
1. **GIỮ NGUYÊN** (copy nguyên văn, không paraphrase) — nếu nội dung đó GÓP PHẦN thỏa mãn ít nhất 1 tiêu chí
2. **SỬA ĐỔI** — nếu nội dung liên quan đến tiêu chí nhưng chưa đạt yêu cầu
3. **LOẠI BỎ** — nếu nội dung KHÔNG liên quan đến bất kỳ tiêu chí nào (không đóng góp vào việc đạt chuẩn)

Ngoài ra: **BỔ SUNG** nội dung mới nếu có tiêu chí chưa được đề cập trong tài liệu gốc.

Quy tắc khi GIỮ NGUYÊN:
- Copy ĐÚNG từng từ, từng câu — KHÔNG paraphrase, KHÔNG viết lại bằng cách diễn đạt khác
- Giữ nguyên: tên công ty, ngày tháng, số hiệu, thuật ngữ gốc

LƯU Ý: Các thông tin cá nhân (tên người, tên công ty, SĐT, email, địa chỉ, chức vụ) KHÔNG phải tiêu chí — giữ nguyên nếu có, không cần thêm nếu thiếu

# {len(criteria)} TIÊU CHÍ CẦN THỎA MÃN:
{criteria_str}

# TÀI LIỆU GỐC (đối chiếu từng đoạn với tiêu chí để quyết định giữ/sửa/bỏ):
{original_ctx or "(Không có tài liệu gốc — tạo mới hoàn toàn)"}

# VẤN ĐỀ ĐÃ PHÁT HIỆN (cần sửa hoặc bổ sung):
{issues_str}

{"# GAP CẦN BỔ SUNG:" + chr(10) + gaps_str if gaps_str else ""}

# THAM CHIẾU:
{ref_ctx[:3000] or "Tiêu chuẩn Halal JAKIM MS 1500:2019 / HDC"}

# FORMAT OUTPUT:
- Tiếng Việt (giữ thuật ngữ Halal tiếng Anh/Mã Lai)
- Plain text, không markdown
- Đánh số: 1. 1.1 1.1.1 cho heading, a) b) c) cho sub-item
- KHÔNG thêm giải thích, ghi chú

Bắt đầu tài liệu ngay:"""

    api_key = OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = OPENROUTER_BASE_URL if OPENROUTER_API_KEY else LLM_BASE_URL
    model = OPENROUTER_MODEL if OPENROUTER_API_KEY else LLM_MODEL
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if OPENROUTER_API_KEY:
        headers["HTTP-Referer"] = "https://fe.silvergem.org"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 8000,
        "stream": True,
    }

    async def stream_gen():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            obj = _json.loads(data)
                            chunk = (obj.get("choices") or [{}])[0].get("delta", {}).get("content")
                            if chunk:
                                yield chunk
                        except:
                            continue
        except Exception as e:
            log.error(f"[generate-document] {e}")
            yield f"\n\n[Lỗi kết nối AI: {e}]"

    return StreamingResponse(stream_gen(), media_type="text/plain")


class ExportDocxRequest(BaseModel):
    content: str
    filename: str = "generated_document"
    title: str = "Tài liệu Halal"
    doc_type: str = ""


@app.post("/generate-document/export-docx")
async def export_docx(
    req: ExportDocxRequest,
    _rate_limit: None = Depends(rate_limit_upload),
    user: dict = Depends(get_current_user),
):
    from templates_docx._registry import build_docx
    import io as _io

    doc = build_docx(
        req.content,
        doc_type=req.doc_type,
        title=req.title,
        filename=req.filename,
    )

    buf = _io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in req.filename)
    safe_name = safe_name.replace(" ", "_").rstrip(".")
    if not safe_name.endswith(".docx"):
        safe_name = safe_name.rsplit(".", 1)[0] + "_improved.docx"

    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.post("/reviews/{filename}")
async def save_review(filename: str, review: AuditorReview):
    import json as _json

    review.filename = filename
    if not review.reviewed_at:
        review.reviewed_at = datetime.utcnow().isoformat()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    path = REVIEWS_DIR / f"{safe_name}.json"
    path.write_text(_json.dumps(review.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"message": "Review saved", "filename": filename}


@app.get("/reviews/{filename}")
async def get_review(filename: str):
    import json as _json

    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    path = REVIEWS_DIR / f"{safe_name}.json"
    if not path.exists():
        return {"exists": False, "review": None}
    data = _json.loads(path.read_text(encoding="utf-8"))
    return {"exists": True, "review": data}


def _run_ingest(path: Path) -> int:
    try:
        client = get_qdrant_client()
        ensure_collection(client, reset=False)
        return ingest_file(path, client)
    except Exception as e:
        log.error(f"Ingest error ({path.name}): {e}")
        return 0


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)  # nosec B104 — containerized service binds inside isolated network
