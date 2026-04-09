import os, sys, shutil, logging, json as _json, secrets, time
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, FileResponse
from pydantic import BaseModel

from starlette.concurrency import run_in_threadpool
from pipeline.query import HalalRAG, embed_query, hybrid_search, build_context, build_system_prompt, SYSTEM_PROMPT, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, LLM_BASE_URL, LLM_MODEL
from pipeline.ingest import ingest_file, ensure_collection, get_qdrant_client
from pipeline.openrouter_client import call_openrouter
from pipeline.evaluate import evaluate_document
from auth.db import init_pool, close_pool
from auth.router import router as auth_router
from auth.admin_router import router as admin_auth_router
from auth.document_router import router as document_router
from auth.jwt_utils import decode_token, get_current_user
from auth.rate_limit import rate_limit_api, rate_limit_upload
from auth.upload_utils import validate_upload

logging.basicConfig(level=logging.INFO)
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
    await init_pool()
    yield
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
    allow_headers=["authorization", "content-type"],
    allow_credentials=True,
    max_age=3600,
)

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

from auth.submission_router import router as submission_router
from auth.certificate_router import router as certificate_router
from auth.notification_router import router as notification_router
app.include_router(auth_router,         prefix="/auth", tags=["auth"])
app.include_router(admin_auth_router,   prefix="/auth", tags=["auth-admin"])
app.include_router(document_router,     prefix="/api",  tags=["documents"])
app.include_router(submission_router,   prefix="/api/submissions", tags=["submissions"])
app.include_router(certificate_router,  prefix="/api/submissions", tags=["certificates"])
app.include_router(notification_router, prefix="/api/notifications", tags=["notifications"])

from supply_chain.supplier_router import router as supplier_router
from supply_chain.material_router import router as material_router
from supply_chain.process_router import router as process_router
from supply_chain.batch_router import router as batch_router
app.include_router(supplier_router,  prefix="/api/supply-chain", tags=["supply-chain"])
app.include_router(material_router,  prefix="/api/supply-chain", tags=["supply-chain"])
app.include_router(process_router,   prefix="/api/supply-chain", tags=["supply-chain"])
app.include_router(batch_router,     prefix="/api/supply-chain", tags=["supply-chain"])

rag = HalalRAG()

UPLOAD_DIR          = Path(os.getenv("UPLOAD_DIR",    "./docs"))
REVIEWS_DIR         = Path(os.getenv("REVIEWS_DIR",   "./reviews"))
TEMPLATES_DIR       = Path(os.getenv("TEMPLATES_DIR", "./admin_templates"))
TEMPLATE_FILES_DIR      = TEMPLATES_DIR / "files"
TEMPLATE_REVISIONS_DIR  = TEMPLATES_DIR / "revisions"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_FILES_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_REVISIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Admin auth ─────────────────────────────────────────────────────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    log.warning("ADMIN_PASSWORD not set — admin panel login disabled")
    ADMIN_PASSWORD = secrets.token_hex(32)  # random = effectively disabled
ADMIN_SECRET   = os.getenv("ADMIN_SECRET", secrets.token_hex(32))
SESSION_TTL = 8 * 3600             # 8 hours
_SESSIONS_FILE = Path("data/admin_sessions.json")

def _load_sessions() -> Dict[str, float]:
    try:
        if _SESSIONS_FILE.exists():
            raw = _json.loads(_SESSIONS_FILE.read_text())
            # Auto-clean expired sessions
            now = time.time()
            cleaned = {k: v for k, v in raw.items() if v > now}
            if len(cleaned) != len(raw):
                _SESSIONS_FILE.write_text(_json.dumps(cleaned))
            return cleaned
    except Exception:
        pass
    return {}

def _save_sessions(sessions: Dict[str, float]):
    _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSIONS_FILE.write_text(_json.dumps(sessions))

def _set_session(token: str, expiry: float):
    s = _load_sessions()
    s[token] = expiry
    _save_sessions(s)

def _remove_session(token: str):
    s = _load_sessions()
    s.pop(token, None)
    _save_sessions(s)

def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = auth[7:]
    sessions = _load_sessions()
    exp = sessions.get(token)
    if not exp or time.time() > exp:
        _remove_session(token)
        raise HTTPException(401, "Session expired or invalid")

# ── Halal document type registry ───────────────────────────────────────────────
HALAL_DOC_TYPES: Dict[str, str] = {
    "halal_policy":                 "Halal Policy",
    "has_manual":                   "HAS Manual",
    "internal_halal_committee":     "Internal Halal Committee",
    "company_profile":              "Company Profile",
    "halal_manual":                 "Halal Manual",
    "ingredient_raw_material":      "Ingredient & Raw Material Documentation",
    "process_flow_chart":           "Process Flow Chart",
    "sop_raw_material_receiving":   "SOP - Raw Material Receiving",
    "sop_storage_segregation":      "SOP - Storage and Segregation",
    "sop_production_operation":     "SOP - Production or Service Operation",
    "sop_cleaning_sanitation":      "SOP - Cleaning and Sanitation",
    "sop_handling_nonconformances": "SOP - Handling Non-Conformances",
    "sop_complaint_recall":         "SOP - Complaint and Recall Management",
}

# ── Template caches ────────────────────────────────────────────────────────────
_template_json_cache:   Dict[str, tuple] = {}
_template_files_cache:  Dict[str, tuple] = {}

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
    # Try language-specific dir first, fall back to root dir
    lang_dir = TEMPLATE_FILES_DIR / doc_type / lang
    root_dir = TEMPLATE_FILES_DIR / doc_type
    dir_path = lang_dir if lang_dir.exists() and any(lang_dir.iterdir()) else root_dir

    cache_key = f"{doc_type}_{lang}"
    mtime_sum = _dir_mtime_sum(dir_path)
    cached = _template_files_cache.get(cache_key)
    if cached and cached[1] == mtime_sum:
        return cached[0]
    content = load_template_files_content(dir_path)
    _template_files_cache[cache_key] = (content, mtime_sum)
    log.info(f"[cache] Template files re-extracted for {cache_key} ({len(content)} chars)")
    return content

TOPIC_LIST = [
    "audit_principles", "audit_planning", "audit_types", "audit_team",
    "halal_standard", "non_conformance", "documentation",
    "fiqh_halal", "certification_body", "logistics",
]

class ChatRequest(BaseModel):
    question:     str
    top_k:        int                    = 6
    topic_filter: Optional[str]          = None
    agent_id:     Optional[str]          = "aminra"
    lang:         Optional[str]          = None
    history:      List[Dict[str, Any]]   = []

class ChatResponse(BaseModel):
    question:    str
    answer:      str
    sources:     list
    scores:      list
    chunks_used: int

class IngestStatus(BaseModel):
    filename: str
    chunks:   int
    status:   str

class EvalIssue(BaseModel):
    section:        str
    severity:       str
    issue:          str
    recommendation: str
    reference:      str

class GapAnalysis(BaseModel):
    critical_gaps: List[str] = []
    major_gaps:    List[str] = []
    minor_gaps:    List[str] = []

class RiskFlag(BaseModel):
    text_snippet: str
    risk_type:    str
    severity:     str
    explanation:  str

class Citation(BaseModel):
    standard:   str
    clause:     str
    text:       str
    relevance:  str

class EvaluationReport(BaseModel):
    filename:         str
    doc_type:         str
    doc_type_label:   str
    word_count:       int
    standards_found:  int
    compliance_score: int
    overall_status:   str
    summary:          str
    issues:           list
    strengths:        list
    recommendations:  list
    standards_checked: list
    gap_analysis:     Optional[Dict] = None
    risk_flags:       List[Dict]     = []
    citations:        List[Dict]     = []
    extracted_text:   Optional[str]  = None

class RewriteRequest(BaseModel):
    section_text: str
    issue:        str
    doc_type:     str = "general"

class RewriteResponse(BaseModel):
    original:             str
    rewritten:            str
    explanation:          str
    standards_referenced: List[str] = []

class AuditorReview(BaseModel):
    filename:             str
    reviewer:             str
    notes:                str = ""
    confirmed_issues:     List[str] = []
    false_positives:      List[str] = []
    additional_findings:  List[str] = []
    status:               str = "pending"
    reviewed_at:          str = ""

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class TemplateCriterion(BaseModel):
    id:          str
    name:        str
    description: str
    weight:      int = 10

class DocxMetaItem(BaseModel):
    key:   str = ""
    value: str = ""

class DocxCustomSection(BaseModel):
    title:   str = ""
    content: str = ""   # plain text, one paragraph per line

class DocxConfig(BaseModel):
    # Cover page
    cover_meta:          List[DocxMetaItem] = []
    confidential_label:  str = "TÀI LIỆU NỘI BỘ"
    # Structural sections
    show_toc:            bool = False
    show_revision_table: bool = True
    show_approval_block: bool = True
    # Custom sections before main content
    custom_sections:     List[DocxCustomSection] = []

class TemplateConfig(BaseModel):
    doc_type:            str
    label:               str = ""
    mandatory_criteria:  List[TemplateCriterion] = []
    evaluation_guidance: str = ""
    docx_config:         Optional[DocxConfig] = None
    updated_at:          str = ""

# ── Admin endpoints ────────────────────────────────────────────────────────────

@app.post("/admin/login")
def admin_login(req: AdminLoginRequest, _: None = Depends(rate_limit_api)):
    if req.username != ADMIN_USERNAME or req.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    token = secrets.token_hex(32)
    _set_session(token, time.time() + SESSION_TTL)
    return {"token": token, "expires_in": SESSION_TTL}

@app.post("/admin/logout")
def admin_logout(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        _remove_session(auth[7:])
    return {"message": "Logged out"}

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
            result.append({"doc_type": dt_id, "label": dt_label,
                           "mandatory_criteria": [], "evaluation_guidance": "", "updated_at": ""})
    return {"templates": result}

@app.get("/admin/templates/{doc_type}")
def get_template(doc_type: str, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    p = TEMPLATES_DIR / f"{doc_type}.json"
    if p.exists():
        return _json.loads(p.read_text(encoding="utf-8"))
    return {"doc_type": doc_type, "label": HALAL_DOC_TYPES[doc_type],
            "mandatory_criteria": [], "evaluation_guidance": "", "updated_at": ""}

@app.put("/admin/templates/{doc_type}")
def save_template(doc_type: str, config: TemplateConfig, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    config.doc_type = doc_type
    config.label    = HALAL_DOC_TYPES[doc_type]
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
                    {"name": f.name, "size": f.stat().st_size,
                     "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat()}
                    for f in sorted(d.iterdir()) if f.is_file()
                ]
        # Also include legacy root files (not in vi/en subfolder)
        root = TEMPLATE_FILES_DIR / doc_type
        if root.exists():
            legacy = [
                {"name": f.name, "size": f.stat().st_size,
                 "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat()}
                for f in sorted(root.iterdir()) if f.is_file() and not f.name.endswith(("_vi.docx", "_en.docx"))
            ]
            if legacy:
                result["legacy"] = legacy
        return {"files_by_lang": result}

    if not dir_path.exists():
        return {"files": []}
    files = [
        {"name": f.name, "size": f.stat().st_size,
         "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat()}
        for f in sorted(dir_path.iterdir()) if f.is_file()
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
    doc_type: str, request: Request,
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


# ── Public template endpoints (for document creation) ─────────────────────────

def _find_template_file(doc_type: str, lang: str) -> Optional[Path]:
    """Find template DOCX for a doc_type + language (vi/en)."""
    dir_path = TEMPLATE_FILES_DIR / doc_type
    if not dir_path.exists():
        return None
    # Priority: exact lang suffix → any docx
    for f in dir_path.iterdir():
        if f.suffix.lower() == ".docx" and f.stem.endswith(f"_{lang}"):
            return f
    return None


@app.get("/templates/available")
def list_available_templates():
    """List doc_types that have template files, with language availability."""
    result = []
    for doc_type, label in HALAL_DOC_TYPES.items():
        dir_path = TEMPLATE_FILES_DIR / doc_type
        if not dir_path.exists():
            continue
        vi_file = _find_template_file(doc_type, "vi")
        en_file = _find_template_file(doc_type, "en")
        if vi_file or en_file:
            result.append({
                "doc_type": doc_type,
                "label": label,
                "has_vi": vi_file is not None,
                "has_en": en_file is not None,
                "vi_size": vi_file.stat().st_size if vi_file else None,
                "en_size": en_file.stat().st_size if en_file else None,
            })
    return {"templates": result}


@app.get("/templates/{doc_type}/download")
def download_template(
    doc_type: str,
    lang: str = "vi",
    _: dict = Depends(get_current_user),
):
    """Download template DOCX for a specific language."""
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    if lang not in ("vi", "en"):
        raise HTTPException(400, "Ngôn ngữ không hợp lệ (vi hoặc en)")
    template = _find_template_file(doc_type, lang)
    if not template:
        raise HTTPException(404, f"Template {lang.upper()} chưa được upload cho {doc_type}")
    return FileResponse(
        path=str(template),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=template.name,
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
    if not re.match(r'^[a-z][a-z0-9_]*$', key):
        raise HTTPException(400, "Key chỉ chứa chữ thường, số và dấu gạch dưới, bắt đầu bằng chữ")

    from auth.db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT COUNT(*) FROM custom_placeholders WHERE key=$1", key)
        if existing:
            raise HTTPException(409, f"Placeholder '{key}' đã tồn tại")
        row = await conn.fetchrow(
            "INSERT INTO custom_placeholders (key, label, description, default_value, source) VALUES ($1,$2,$3,$4,$5) RETURNING id",
            key, label, description or None, default_value or None, source or None)

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
        result = await conn.execute("""
            UPDATE custom_placeholders
            SET label = COALESCE(NULLIF($1, ''), label),
                description = $2,
                default_value = $3,
                source = $4
            WHERE key = $5 AND is_system = false
        """, label, description or None, default_value or None, source or None, key)
    if result == "UPDATE 0":
        raise HTTPException(400, "Không thể sửa placeholder hệ thống hoặc không tồn tại")
    return {"message": f"Đã cập nhật placeholder {key}"}


@app.delete("/admin/placeholders/{key}")
async def delete_placeholder(key: str, request: Request):
    _require_admin(request)
    from auth.db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM custom_placeholders WHERE key=$1 AND is_system=false", key)
    if result == "DELETE 0":
        raise HTTPException(400, "Không thể xoá placeholder hệ thống hoặc không tồn tại")
    return {"message": f"Đã xoá placeholder {key}"}


# ── Public: get all placeholders (for template creation) ─────────────────────

@app.get("/placeholders")
async def get_all_placeholders():
    from auth.db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, label, description, default_value, source, is_system FROM custom_placeholders ORDER BY is_system DESC, created_at")
    return {"placeholders": [dict(r) for r in rows]}


# ── Admin user management ──────────────────────────────────────────────────────

class AdminCreateUserRequest(BaseModel):
    email: str
    password: str
    company_name: str
    role: str           # 'business' | 'provider'
    company_code: Optional[str] = None
    status: str = "active"

class AdminUpdateUserRequest(BaseModel):
    company_name: Optional[str] = None
    company_code: Optional[str] = None
    status: Optional[str] = None      # active | pending | suspended
    role: Optional[str] = None
    is_owner: Optional[bool] = None
    password: Optional[str] = None    # if set → rehash and update

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
            conditions.append(f"role = ${idx}"); params.append(role); idx += 1
        if status:
            conditions.append(f"status = ${idx}"); params.append(status); idx += 1
        if q:
            conditions.append(f"(email ILIKE ${idx} OR company_name ILIKE ${idx})")
            params.append(f"%{q}%"); idx += 1
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
    _require_admin(request)
    from auth.db import get_pool
    from auth.password import hash_password
    import uuid as _uuid2
    pool = get_pool()
    pw_hash = hash_password(body.password)
    user_id = str(_uuid2.uuid4())
    tenant_id = user_id if body.role == "business" else None
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email=$1", body.email)
        if existing:
            raise HTTPException(400, "Email đã tồn tại")
        await conn.execute(
            """INSERT INTO users
               (id, email, password_hash, role, company_name, company_code,
                status, is_owner, tenant_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
            user_id, body.email, pw_hash, body.role,
            body.company_name, body.company_code,
            body.status, True, tenant_id,
        )
        row = await conn.fetchrow(
            "SELECT id,email,role,company_name,company_code,status,is_owner,tenant_id,created_at FROM users WHERE id=$1", user_id
        )
    return dict(row)

@app.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, request: Request, body: AdminUpdateUserRequest):
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
            ("status",       body.status),
            ("role",         body.role),
            ("is_owner",     body.is_owner),
        ]:
            if val is not None:
                updates.append(f"{field} = ${idx}"); params.append(val); idx += 1
        if body.password:
            from auth.password import hash_password
            updates.append(f"password_hash = ${idx}"); params.append(hash_password(body.password)); idx += 1
        if not updates:
            return dict(row)
        params.append(user_id)
        await conn.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}", *params
        )
        row = await conn.fetchrow(
            "SELECT id,email,role,company_name,company_code,status,is_owner,tenant_id,created_at FROM users WHERE id=$1", user_id
        )
    return dict(row)

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    _require_admin(request)
    if user_id == "54182089-3a6d-458a-994d-93ac4e0c504f":  # guard: never delete seeded admin
        raise HTTPException(403, "Không thể xoá tài khoản admin gốc")
    from auth.db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, role, tenant_id FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(404, "User không tồn tại")
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
        info  = client.get_collection(COLLECTION_NAME)
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
        question=result.question, answer=result.answer,
        sources=[], scores=result.scores, chunks_used=result.chunks_used,
    )

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, _: None = Depends(rate_limit_api)):
    if not req.question.strip():
        raise HTTPException(400, "question khong duoc de trong")

    # RAG search (sync ML calls → thread pool)
    query_data = await run_in_threadpool(embed_query, req.question)
    hits       = await run_in_threadpool(hybrid_search, query_data, req.top_k, req.topic_filter)
    context    = await run_in_threadpool(build_context, hits)

    sys_prompt = build_system_prompt(req.lang)
    prompt = f"{sys_prompt}\n\nCONTEXT:\n{context}\n\nCÂU HỎI: {req.question}"

    api_key  = OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = OPENROUTER_BASE_URL if OPENROUTER_API_KEY else LLM_BASE_URL
    model    = OPENROUTER_MODEL    if OPENROUTER_API_KEY else LLM_MODEL
    headers  = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if OPENROUTER_API_KEY:
        headers["HTTP-Referer"] = "https://fe.silvergem.org"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
        "stream": True,
    }

    async def generate():
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0)
            ) as client:
                async with client.stream(
                    "POST", f"{base_url}/chat/completions",
                    headers=headers, json=payload,
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
async def ingest_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), _: None = Depends(rate_limit_upload)):
    content = await validate_upload(file)
    save_path = UPLOAD_DIR / file.filename
    if not save_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(400, "Invalid file path")
    save_path.write_bytes(content)
    background_tasks.add_task(_run_ingest, save_path)
    return IngestStatus(filename=file.filename, chunks=0, status="queued")

@app.post("/evaluate", response_model=EvaluationReport)
async def evaluate_doc(
    request: Request,
    file: UploadFile = File(...),
    _rate_limit: None = Depends(rate_limit_upload),
    doc_type: Optional[str] = Form(None),
    previous_context: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
):
    content = await validate_upload(file)
    suffix  = Path(file.filename or "").suffix.lower()

    # Extract JWT user if present (optional — anonymous evaluate still works)
    jwt_user = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            jwt_user = decode_token(auth_header[7:])
        except Exception:
            pass  # treat as anonymous

    eval_lang = lang or "vi"
    forced_doc_type   = doc_type if doc_type and doc_type in HALAL_DOC_TYPES else None
    forced_doc_label  = HALAL_DOC_TYPES.get(forced_doc_type, "") if forced_doc_type else ""
    template_criteria         = _load_template(forced_doc_type) if forced_doc_type else None
    template_files_content    = _load_template_files_content(forced_doc_type, eval_lang) if forced_doc_type else ""
    # Use lang-specific dir if exists, fallback to root
    template_files_dir        = None
    if forced_doc_type:
        lang_dir = TEMPLATE_FILES_DIR / forced_doc_type / eval_lang
        root_dir = TEMPLATE_FILES_DIR / forced_doc_type
        template_files_dir = lang_dir if lang_dir.exists() else root_dir

    import tempfile, uuid as _uuid
    file_bytes = content
    file_size  = len(file_bytes)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = evaluate_document(
            tmp_path, file.filename,
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

    report = EvaluationReport(**{
        "filename":         result.get("filename", file.filename),
        "doc_type":         result.get("doc_type", "general"),
        "doc_type_label":   result.get("doc_type_label", "Tài liệu chung"),
        "word_count":       result.get("word_count", 0),
        "standards_found":  result.get("standards_found", 0),
        "compliance_score": result.get("compliance_score", 0),
        "overall_status":   result.get("overall_status", "needs_review"),
        "summary":          result.get("summary", ""),
        "issues":           result.get("issues", []),
        "strengths":        result.get("strengths", []),
        "recommendations":  result.get("recommendations", []),
        "standards_checked":result.get("standards_checked", []),
        "gap_analysis":     result.get("gap_analysis"),
        "risk_flags":       result.get("risk_flags", []),
        "citations":        result.get("citations", []),
        "extracted_text":   result.get("extracted_text"),
    })

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
                doc_uuid   = str(_uuid.uuid4())
                safe_name  = "".join(c if c.isalnum() or c in "._- " else "_" for c in file.filename).strip()
                save_path  = tenant_dir / f"{doc_uuid}_{safe_name}"
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
                    save_path.name, file.filename, str(save_path),
                    file_size, mime,
                    jwt_user["sub"], jwt_user["tenant_id"],
                    result.get("doc_type"), result.get("compliance_score"),
                    _json_mod.dumps(result, ensure_ascii=False),
                )
                log.info(f"[documents] Saved {file.filename} for tenant {jwt_user['tenant_id']}")
        except Exception as e:
            log.error(f"[documents] Failed to save to DB: {e}")
            # Don't fail the evaluate response — just log

    return report


@app.post("/rewrite", response_model=RewriteResponse)
async def suggest_rewrite(req: RewriteRequest):
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
  "original": "{req.section_text[:200].replace(chr(10), ' ')}...",
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
    doc_type:       str
    doc_type_label: str
    extracted_text: str = ""
    issues:         list = []
    recommendations: list = []
    gap_analysis:   Optional[Dict] = None

@app.post("/generate-document")
async def generate_document(req: GenerateDocRequest):
    template  = _load_template(req.doc_type)
    criteria  = template.get("mandatory_criteria", []) if template else []
    ref_ctx   = _load_template_files_content(req.doc_type) if req.doc_type else ""

    criteria_str = "\n".join(
        f"{i+1}. **{c.get('name','')}** (trọng số {c.get('weight',10)}pt): {c.get('description','')}"
        for i, c in enumerate(criteria)
    ) or "Áp dụng tiêu chuẩn Halal JAKIM/HDC đầy đủ"

    issues_str = "\n".join(
        f"- [{it.get('severity','').upper()}] {it.get('section','')}: {it.get('issue','')} → {it.get('recommendation','')}"
        for it in req.issues[:20]
    ) or "Không phát hiện vấn đề cụ thể"

    gaps_str = ""
    if req.gap_analysis:
        cg = req.gap_analysis.get("critical_gaps", [])
        mg = req.gap_analysis.get("major_gaps", [])
        if cg: gaps_str += "Critical: " + "; ".join(cg[:5]) + "\n"
        if mg: gaps_str += "Major: "    + "; ".join(mg[:5])

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

    api_key  = OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = OPENROUTER_BASE_URL if OPENROUTER_API_KEY else LLM_BASE_URL
    model    = OPENROUTER_MODEL    if OPENROUTER_API_KEY else LLM_MODEL
    headers  = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
                    "POST", f"{base_url}/chat/completions",
                    headers=headers, json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "): continue
                        data = line[6:]
                        if data == "[DONE]": break
                        try:
                            obj = _json.loads(data)
                            chunk = (obj.get("choices") or [{}])[0].get("delta", {}).get("content")
                            if chunk: yield chunk
                        except: continue
        except Exception as e:
            log.error(f"[generate-document] {e}")
            yield f"\n\n[Lỗi kết nối AI: {e}]"

    return StreamingResponse(stream_gen(), media_type="text/plain")


class ExportDocxRequest(BaseModel):
    content:  str
    filename: str = "generated_document"
    title:    str = "Tài liệu Halal"
    doc_type: str = ""

@app.post("/generate-document/export-docx")
async def export_docx(req: ExportDocxRequest):
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
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
