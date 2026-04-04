import os, sys, shutil, logging, json as _json, secrets, time
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from starlette.concurrency import run_in_threadpool
from pipeline.query import HalalRAG, embed_query, hybrid_search, build_context, build_system_prompt, SYSTEM_PROMPT, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, LLM_BASE_URL, LLM_MODEL
from pipeline.ingest import ingest_file, ensure_collection, get_qdrant_client
from pipeline.openrouter_client import call_openrouter
# Ollama removed - using external APIs only
from pipeline.evaluate import evaluate_document

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aminra.api")

app = FastAPI(
    title="Aminra — Halal Certification AI",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["https://fe.silvergem.org", "http://fe.silvergem.org", "http://localhost:3000", "https://mukjizat.silvergem.org", "http://mukjizat.silvergem.org", "http://localhost:3001"], allow_methods=["*"], allow_headers=["*"])

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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "aminra2026")
ADMIN_SECRET   = os.getenv("ADMIN_SECRET",   secrets.token_hex(32))
_sessions: Dict[str, float] = {}   # token → expiry unix timestamp
SESSION_TTL = 8 * 3600             # 8 hours

def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = auth[7:]
    exp = _sessions.get(token)
    if not exp or time.time() > exp:
        _sessions.pop(token, None)
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

def _load_template_files_content(doc_type: str) -> str:
    from pipeline.evaluate import load_template_files_content
    dir_path = TEMPLATE_FILES_DIR / doc_type
    mtime_sum = _dir_mtime_sum(dir_path)
    cached = _template_files_cache.get(doc_type)
    if cached and cached[1] == mtime_sum:
        return cached[0]
    content = load_template_files_content(dir_path)
    _template_files_cache[doc_type] = (content, mtime_sum)
    log.info(f"[cache] Template files re-extracted for {doc_type} ({len(content)} chars)")
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

class TemplateConfig(BaseModel):
    doc_type:            str
    label:               str = ""
    mandatory_criteria:  List[TemplateCriterion] = []
    evaluation_guidance: str = ""
    updated_at:          str = ""

# ── Admin endpoints ────────────────────────────────────────────────────────────

@app.post("/admin/login")
def admin_login(req: AdminLoginRequest):
    if req.username != ADMIN_USERNAME or req.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    token = secrets.token_hex(32)
    _sessions[token] = time.time() + SESSION_TTL
    return {"token": token, "expires_in": SESSION_TTL}

@app.post("/admin/logout")
def admin_logout(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        _sessions.pop(auth[7:], None)
    return {"message": "Logged out"}

@app.get("/admin/verify")
def admin_verify(request: Request):
    try:
        _require_admin(request)
        return {"valid": True}
    except HTTPException:
        return {"valid": False}

@app.get("/admin/doc-types")
def list_doc_types():
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
def list_template_files(doc_type: str, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    dir_path = TEMPLATE_FILES_DIR / doc_type
    if not dir_path.exists():
        return {"files": []}
    files = [
        {"name": f.name, "size": f.stat().st_size, "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat()}
        for f in sorted(dir_path.iterdir()) if f.is_file()
    ]
    return {"files": files}

@app.post("/admin/templates/{doc_type}/files")
async def upload_template_file(doc_type: str, request: Request, file: UploadFile = File(...)):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    allowed = {".pdf", ".pptx", ".ppt", ".docx", ".odt", ".txt", ".md"}
    suffix  = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Định dạng không hỗ trợ: {suffix}")
    dir_path = TEMPLATE_FILES_DIR / doc_type
    dir_path.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in file.filename).strip()
    save_path = dir_path / safe_name
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    _template_files_cache.pop(doc_type, None)
    _append_revision(doc_type, {
        "action": "upload",
        "filename": safe_name,
        "size": save_path.stat().st_size,
        "timestamp": datetime.utcnow().isoformat(),
    })
    log.info(f"[admin] Template file uploaded: {doc_type}/{safe_name}")
    return {"message": "File uploaded", "filename": safe_name, "doc_type": doc_type}

@app.delete("/admin/templates/{doc_type}/files/{filename}")
def delete_template_file(doc_type: str, filename: str, request: Request):
    _require_admin(request)
    if doc_type not in HALAL_DOC_TYPES:
        raise HTTPException(404, f"Loại tài liệu không tồn tại: {doc_type}")
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename).strip()
    file_path = TEMPLATE_FILES_DIR / doc_type / safe_name
    if not file_path.exists():
        raise HTTPException(404, "File không tồn tại")
    file_path.unlink()
    _template_files_cache.pop(doc_type, None)
    _append_revision(doc_type, {
        "action": "delete",
        "filename": safe_name,
        "timestamp": datetime.utcnow().isoformat(),
    })
    log.info(f"[admin] Template file deleted: {doc_type}/{safe_name}")
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

@app.get("/health")
def health():
    return {"status": "ok", "service": "Aminra Halal Certification AI"}

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
def chat(req: ChatRequest):
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
async def chat_stream(req: ChatRequest):
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
async def ingest_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    allowed = {".pptx", ".ppt", ".pdf", ".txt", ".md", ".docx", ".odt"}
    suffix  = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Dinh dang khong ho tro: {suffix}")
    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    background_tasks.add_task(_run_ingest, save_path)
    return IngestStatus(filename=file.filename, chunks=0, status="queued")

@app.post("/evaluate", response_model=EvaluationReport)
async def evaluate_doc(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    previous_context: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
):
    allowed = {".pptx", ".ppt", ".pdf", ".txt", ".md", ".docx", ".odt"}
    suffix  = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Dinh dang khong ho tro: {suffix}")

    forced_doc_type   = doc_type if doc_type and doc_type in HALAL_DOC_TYPES else None
    forced_doc_label  = HALAL_DOC_TYPES.get(forced_doc_type, "") if forced_doc_type else ""
    template_criteria         = _load_template(forced_doc_type) if forced_doc_type else None
    template_files_content    = _load_template_files_content(forced_doc_type) if forced_doc_type else ""
    template_files_dir        = (TEMPLATE_FILES_DIR / forced_doc_type) if forced_doc_type else None

    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
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

    return EvaluationReport(**{
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
    })


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
