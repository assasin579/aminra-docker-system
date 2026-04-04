"""
Document Evaluation Pipeline — Option C (Hybrid)
=================================================
Đánh giá tài liệu tải lên bằng cách so sánh với tiêu chuẩn Halal trong KB.
"""

import os, json, re, logging
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger("mukjizat.evaluate")

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL    = os.getenv("OPENROUTER_MODEL",    "deepseek/deepseek-chat")

DEEPSEEK_API_KEY    = os.getenv("DEEPSEEK_API_KEY")
LLM_BASE_URL        = os.getenv("LLM_BASE_URL",    "https://api.deepseek.com")
LLM_MODEL           = os.getenv("LLM_MODEL",       "deepseek-chat")

# ── Document type detection ────────────────────────────────────────────────────

DOC_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "ingredient_list": [
        "thành phần", "nguyên liệu", "ingredient", "raw material",
        "phụ gia", "additive", "e-number", "hương liệu", "flavour", "colour",
        "preservative", "emulsifier", "chất bảo quản", "chất nhũ hóa",
    ],
    "sop": [
        "quy trình", "procedure", "sop", "bước", "step",
        "hướng dẫn thao tác", "work instruction", "vệ sinh", "cleaning",
        "sanitizing", "kiểm soát", "control",
    ],
    "certification": [
        "chứng nhận", "certificate", "certification", "halal cert",
        "certificate no", "issued by", "valid until", "expiry", "ngày hết hạn",
        "cơ quan chứng nhận",
    ],
    "supplier_doc": [
        "nhà cung cấp", "supplier", "vendor", "company profile",
        "nhà sản xuất", "manufacturer", "plant address", "approval",
    ],
    "audit_report": [
        "audit", "đánh giá", "finding", "non-conformance", "corrective action",
        "car", "ncr", "observation", "recommendation", "scope of audit",
    ],
    "product_spec": [
        "đặc tính sản phẩm", "product specification", "spec",
        "composition", "nutritional", "dinh dưỡng", "shelf life",
    ],
}

DOC_TYPE_LABELS = {
    "ingredient_list": "Danh sách thành phần / Nguyên liệu",
    "sop": "Quy trình thao tác chuẩn (SOP)",
    "certification": "Giấy chứng nhận Halal",
    "supplier_doc": "Hồ sơ nhà cung cấp",
    "audit_report": "Báo cáo đánh giá (Audit Report)",
    "product_spec": "Đặc tính kỹ thuật sản phẩm",
    "general": "Tài liệu chung",
}


def detect_doc_type(text: str) -> str:
    t = text.lower()
    scores = {k: sum(1 for kw in v if kw in t) for k, v in DOC_TYPE_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ── Text extraction with persistent disk cache ────────────────────────────────

import hashlib as _hashlib

_DOC_CACHE_MAX = 50  # giữ tối đa 50 entry
_DOC_CACHE_DIR = Path(os.getenv("DOC_CACHE_DIR", "./doc_text_cache"))


def _file_sha256(path: Path) -> str:
    h = _hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_path(key: str) -> Path:
    _DOC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _DOC_CACHE_DIR / f"{key}.json"


def extract_text_from_file(path: Path) -> tuple:
    """Return (full_text, source_type). Disk-cached by SHA256 — survives restarts."""
    key = _file_sha256(path)
    cp = _cache_path(key)

    if cp.exists():
        try:
            data = json.loads(cp.read_text(encoding="utf-8"))
            log.info(f"[extract] Disk cache hit: {path.name}")
            return data["text"], data["source_type"]
        except Exception:
            cp.unlink(missing_ok=True)

    from pipeline.ingest import extract
    source_type, pages = extract(path)
    full_text = "\n\n".join(p["text"] for p in pages if p.get("text"))

    try:
        cp.write_text(json.dumps({"text": full_text, "source_type": source_type},
                                 ensure_ascii=False), encoding="utf-8")
        # Evict oldest files if over limit
        cache_files = sorted(_DOC_CACHE_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for old in cache_files[:-_DOC_CACHE_MAX]:
            old.unlink(missing_ok=True)
    except Exception as e:
        log.warning(f"[extract] Could not write cache: {e}")

    log.info(f"[extract] Extracted & cached: {path.name} ({len(full_text.split())} words)")
    return full_text.strip(), source_type


# ── KB search ─────────────────────────────────────────────────────────────────

def load_template_files_content(template_files_dir: Path) -> str:
    """Extract and concatenate text from all admin-uploaded template files for a doc type."""
    if not template_files_dir.exists():
        return ""
    parts = []
    for f in sorted(template_files_dir.iterdir()):
        if not f.is_file():
            continue
        try:
            text, _ = extract_text_from_file(f)
            if text.strip():
                parts.append(f"--- {f.name} ---\n{text.strip()}")
        except Exception as e:
            log.warning(f"[evaluate] Could not read template file {f.name}: {e}")
    return "\n\n".join(parts)


# ── Prompt building ───────────────────────────────────────────────────────────

EVAL_LANG_INSTRUCTIONS: dict = {
    "en": (
        "Respond entirely in English. All text fields in the JSON (summary, issues, "
        "strengths, recommendations, gap_analysis, risk_flags, citations) must be in English."
    ),
    "ms": (
        "Jawab sepenuhnya dalam Bahasa Melayu. Semua medan teks dalam JSON mesti dalam Bahasa Melayu."
    ),
    "ar": (
        "أجب بالكامل باللغة العربية. يجب أن تكون جميع حقول النص في JSON باللغة العربية."
    ),
    "vi": (
        "Dùng tiếng Việt cho mọi nội dung văn bản trong JSON."
    ),
}


def build_eval_prompt(doc_text: str, doc_type: str, filename: str,
                      template_criteria: Optional[Dict] = None,
                      template_files_content: str = "",
                      previous_context: Optional[str] = None,
                      lang: Optional[str] = None) -> str:
    doc_excerpt = " ".join(doc_text.split()[:2000])

    # Build reference section — ONLY from admin-provided content
    reference_ctx = ""
    if template_files_content.strip():
        # Truncate to ~4000 words to stay within token limits
        words = template_files_content.split()
        truncated = " ".join(words[:4000])
        reference_ctx += f"\n=== TÀI LIỆU MẪU THAM CHIẾU (do admin cung cấp) ===\n{truncated}\n"

    criteria_ctx = ""
    if template_criteria:
        criteria_list = template_criteria.get("mandatory_criteria", [])
        guidance      = template_criteria.get("evaluation_guidance", "")
        if criteria_list:
            criteria_ctx += "\n=== TIÊU CHÍ CHẤM ĐIỂM BẮT BUỘC ===\n"
            for c in criteria_list:
                criteria_ctx += f"- [{c.get('weight', 10)} điểm] {c['name']}: {c.get('description', '')}\n"
        if guidance:
            criteria_ctx += f"\n=== HƯỚNG DẪN ĐÁNH GIÁ ===\n{guidance}\n"

    if not reference_ctx and not criteria_ctx:
        reference_ctx = "(Chưa có tài liệu mẫu hoặc tiêu chí nào được admin cung cấp cho loại tài liệu này)"

    prev_ctx = ""
    if previous_context:
        prev_ctx = f"\n=== PHÂN TÍCH LẦN TRƯỚC ===\n{previous_context}\nHãy đặc biệt chú ý đến những thay đổi so với lần đánh giá trước.\n"

    lang_code = (lang or "vi").split("-")[0].lower()
    lang_instr = EVAL_LANG_INSTRUCTIONS.get(lang_code, EVAL_LANG_INSTRUCTIONS["vi"])

    return f"""Bạn là công cụ đánh giá tài liệu. Nhiệm vụ duy nhất của bạn là đối chiếu tài liệu được upload với tài liệu mẫu và tiêu chí được admin cung cấp bên dưới.

NGÔN NGỮ ĐẦU RA: {lang_instr}

QUAN TRỌNG: Chỉ sử dụng nội dung trong phần "TÀI LIỆU MẪU THAM CHIẾU" và "TIÊU CHÍ CHẤM ĐIỂM" làm cơ sở đánh giá duy nhất. Không được sử dụng kiến thức bên ngoài, không tham chiếu bất kỳ tiêu chuẩn nào không được cung cấp trong prompt này.

=== TÀI LIỆU CẦN ĐÁNH GIÁ ===
Tên file: {filename}
Loại tài liệu: {DOC_TYPE_LABELS.get(doc_type, doc_type)}

{doc_excerpt}
{reference_ctx}{criteria_ctx}{prev_ctx}

=== YÊU CẦU ===
Đối chiếu tài liệu trên với tài liệu mẫu và tiêu chí được cung cấp. Trả về KẾT QUẢ DUY NHẤT là một JSON object hợp lệ với cấu trúc CHÍNH XÁC sau:
{{
  "compliance_score": <số nguyên 0-100, dựa hoàn toàn vào mức độ đáp ứng tiêu chí được cung cấp>,
  "overall_status": "<compliant|needs_review|non_compliant>",
  "summary": "<tóm tắt 1-2 câu về mức độ phù hợp với tài liệu mẫu và tiêu chí>",
  "issues": [
    {{
      "section": "<phần/mục trong tài liệu được đánh giá>",
      "severity": "<critical|major|minor>",
      "issue": "<mô tả cụ thể sự khác biệt hoặc thiếu sót so với tài liệu mẫu/tiêu chí>",
      "recommendation": "<hướng dẫn khắc phục dựa trên tài liệu mẫu>",
      "reference": "<tên file mẫu hoặc tên tiêu chí tham chiếu>"
    }}
  ],
  "strengths": ["<điểm đáp ứng tốt so với tài liệu mẫu/tiêu chí 1>", "<điểm mạnh 2>"],
  "recommendations": ["<khuyến nghị cải thiện dựa trên tài liệu mẫu 1>", "<khuyến nghị 2>"],
  "standards_checked": ["<tên file mẫu hoặc tiêu chí đã đối chiếu>"],
  "gap_analysis": {{
    "critical_gaps": ["<yêu cầu bắt buộc trong tài liệu mẫu/tiêu chí hoàn toàn vắng mặt>"],
    "major_gaps": ["<yêu cầu quan trọng còn thiếu hoặc không đầy đủ>"],
    "minor_gaps": ["<điểm cần cải thiện nhỏ>"]
  }},
  "risk_flags": [
    {{
      "text_snippet": "<trích đúng 20-60 từ từ tài liệu gốc có vấn đề>",
      "risk_type": "<prohibited_ingredient|contamination|unclear_sourcing|process_risk|missing_certification|cross_contamination>",
      "severity": "<critical|high|medium|low>",
      "explanation": "<giải thích tại sao đoạn này không đáp ứng yêu cầu trong tài liệu mẫu>"
    }}
  ],
  "citations": [
    {{
      "standard": "<tên file mẫu hoặc tiêu chí được tham chiếu>",
      "clause": "<mục hoặc phần trong tài liệu mẫu>",
      "text": "<trích dẫn từ tài liệu mẫu>",
      "relevance": "<giải thích cách điều này áp dụng vào đánh giá>"
    }}
  ]
}}

Quy tắc điểm: 80-100 = compliant, 50-79 = needs_review, 0-49 = non_compliant.
Nếu không có tài liệu mẫu hoặc tiêu chí, ghi rõ trong summary và đặt compliance_score = 0.
{lang_instr} Chỉ trả về JSON, không có text ngoài JSON."""


# ── LLM calls ─────────────────────────────────────────────────────────────────

def _post_llm(url: str, headers: dict, payload: dict, timeout: int = 90) -> str:
    import requests
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_llm_json(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://mukjizat.silvergem.org",
        "X-Title": "Mukjizat Halal Evaluator",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    return _post_llm(f"{OPENROUTER_BASE_URL}/chat/completions", headers, payload)


def call_deepseek_json(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    return _post_llm(f"{LLM_BASE_URL}/chat/completions", headers, payload)


# ── JSON parsing ──────────────────────────────────────────────────────────────

def parse_json_safe(raw: str) -> dict:
    raw = raw.strip()
    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Extract first {...} block
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # Fallback
    log.warning("Could not parse LLM JSON, returning fallback structure")
    return {
        "compliance_score": 50,
        "overall_status": "needs_review",
        "summary": "Không thể phân tích tự động. Vui lòng xem xét tài liệu thủ công.",
        "issues": [],
        "strengths": [],
        "recommendations": ["Cần xem xét thủ công tài liệu này"],
        "standards_checked": [],
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def evaluate_document(path: Path, original_filename: str,
                      forced_doc_type: Optional[str] = None,
                      forced_doc_label: str = "",
                      template_criteria: Optional[Dict] = None,
                      template_files_dir: Optional[Path] = None,
                      template_files_content: str = "",
                      previous_context: Optional[str] = None,
                      lang: Optional[str] = None) -> dict:
    """
    Full evaluation pipeline.
    Evaluation is based solely on admin-provided template files and criteria.
    template_files_content: pre-extracted content from cache (skips disk re-read).
    Returns structured dict (EvaluationReport).
    """
    log.info(f"[evaluate] Starting: {original_filename}")

    # 1. Extract text from uploaded document
    try:
        doc_text, source_type = extract_text_from_file(path)
    except Exception as e:
        raise ValueError(f"Không thể đọc tài liệu: {e}")

    word_count = len(doc_text.split())
    if word_count < 10:
        raise ValueError("Tài liệu quá ngắn hoặc không có nội dung văn bản có thể đọc được")

    # 2. Detect or use forced doc type
    if forced_doc_type:
        doc_type = forced_doc_type
        log.info(f"[evaluate] Type={doc_type} (user-selected), words={word_count}")
    else:
        doc_type = detect_doc_type(doc_text)
        log.info(f"[evaluate] Type={doc_type} (auto-detected), words={word_count}")

    # 3. Use pre-cached template content; fallback to disk read if not provided
    if not template_files_content and template_files_dir:
        template_files_content = load_template_files_content(template_files_dir)
    template_files_count = (
        sum(1 for f in template_files_dir.iterdir() if f.is_file())
        if template_files_dir and template_files_dir.exists() else 0
    )
    log.info(f"[evaluate] Template content: {len(template_files_content)} chars, files: {template_files_count}")

    # 4. Build prompt and call LLM
    prompt = build_eval_prompt(
        doc_text, doc_type, original_filename,
        template_criteria=template_criteria,
        template_files_content=template_files_content,
        previous_context=previous_context,
        lang=lang,
    )

    raw = None
    try:
        raw = call_llm_json(prompt)
        log.info("[evaluate] OpenRouter succeeded")
    except Exception as e:
        log.warning(f"[evaluate] OpenRouter failed ({e}), trying DeepSeek...")
        try:
            raw = call_deepseek_json(prompt)
            log.info("[evaluate] DeepSeek succeeded")
        except Exception as e2:
            raise ValueError(f"LLM evaluation failed: {e2}")

    # 5. Parse and enrich
    result = parse_json_safe(raw)
    result.update({
        "filename":        original_filename,
        "doc_type":        doc_type,
        "doc_type_label":  forced_doc_label or DOC_TYPE_LABELS.get(doc_type, doc_type),
        "word_count":      word_count,
        "standards_found": template_files_count,
        "gap_analysis":    result.get("gap_analysis") if isinstance(result.get("gap_analysis"), dict)
                           else {"critical_gaps": [], "major_gaps": [], "minor_gaps": []},
        "risk_flags":      result.get("risk_flags") if isinstance(result.get("risk_flags"), list)
                           else [],
        "citations":       result.get("citations") if isinstance(result.get("citations"), list)
                           else [],
    })

    log.info(f"[evaluate] Done. Score={result.get('compliance_score')}, Status={result.get('overall_status')}")
    return result
