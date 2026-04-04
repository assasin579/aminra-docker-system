import os, sys, json, http.client, urllib.parse, logging, re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("aminra.query")

# ── Configuration ──────────────────────────────────────────────────────────────
QDRANT_URL      = os.getenv("QDRANT_URL",      "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "halal_kb")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "intfloat/multilingual-e5-base")
LLM_BACKEND     = os.getenv("LLM_BACKEND",     "openrouter").lower()
TOP_K           = int(os.getenv("TOP_K",       "12"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.08"))
RERANK_TOP_K    = int(os.getenv("RERANK_TOP_K", "6"))

# DeepSeek (fallback)
LLM_BASE_URL    = os.getenv("LLM_BASE_URL",    "https://api.deepseek.com")
LLM_MODEL       = os.getenv("LLM_MODEL",       "deepseek-chat")
DEEPSEEK_API_KEY= os.getenv("DEEPSEEK_API_KEY")

# OpenRouter (primary)
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL    = os.getenv("OPENROUTER_MODEL",    "deepseek/deepseek-chat")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")



log.info(f"LLM Backend: {LLM_BACKEND.upper()}")

SYSTEM_PROMPT = """Bạn là Aminra - chuyên gia tư vấn chứng nhận Halal.

NGUYÊN TẮC:
- Dựa hoàn toàn vào ngữ cảnh được cung cấp
- Đủ ý, không bỏ sót điểm quan trọng — đặc biệt với câu hỏi liệt kê thì phải liệt kê đầy đủ
- Không trích dẫn tên file, không ghi nguồn
- Nếu không có thông tin trong context: nói ngắn gọn là không tìm thấy

CẤU TRÚC BẮT BUỘC:
1. **Tóm tắt** (1-2 câu trả lời thẳng vào câu hỏi)
2. **Nội dung chính** (bullet points — đủ ý, mỗi điểm 1-2 câu ngắn)
3. **Gợi ý** (1-2 câu thực tế giúp doanh nghiệp áp dụng)"""

LANG_INSTRUCTIONS: dict = {
    "en": "Respond entirely in English.",
    "ms": "Jawab sepenuhnya dalam Bahasa Melayu.",
    "ar": "أجب بالكامل باللغة العربية.",
    "vi": "Trả lời hoàn toàn bằng tiếng Việt.",
}

def build_system_prompt(lang: str | None) -> str:
    lang_code = (lang or "vi").split("-")[0].lower()
    lang_instr = LANG_INSTRUCTIONS.get(lang_code, LANG_INSTRUCTIONS["vi"])
    return SYSTEM_PROMPT + f"\n\nNGÔN NGỮ: {lang_instr}"

# Load synonyms
SYNONYMS_PATH = os.path.join(os.path.dirname(__file__), "synonyms.json")
try:
    with open(SYNONYMS_PATH, 'r', encoding='utf-8') as f:
        SYNONYMS = json.load(f)
except FileNotFoundError:
    SYNONYMS = {"halal_terms": {}, "query_types": {}}

_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        embed_model = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        log.info(f"Dang tai embedding model: {embed_model} ...")
        _encoder = SentenceTransformer(embed_model)
        log.info("  Model da tai xong.")
    return _encoder

def classify_query_type(text: str) -> str:
    """Phân loại loại query để áp dụng strategy phù hợp."""
    text_lower = text.lower()
    
    for qtype, keywords in SYNONYMS["query_types"].items():
        if any(keyword in text_lower for keyword in keywords):
            return qtype
    
    # Default classification
    if any(word in text_lower for word in ["là gì", "what is", "define", "explain", "khái niệm"]):
        return "definition"
    elif any(word in text_lower for word in ["cách", "how to", "quy trình", "bước"]):
        return "procedure"
    elif any(word in text_lower for word in ["yêu cầu", "requirements", "tiêu chuẩn"]):
        return "requirement"
    
    return "general"

def expand_query_with_synonyms(text: str) -> List[str]:
    """Mở rộng query với synonyms từ domain knowledge."""
    text_lower = text.lower()
    expanded_queries = [text]  # Luôn giữ bản gốc
    
    # Expand với halal terms
    for term, synonyms in SYNONYMS["halal_terms"].items():
        if term in text_lower:
            for synonym in synonyms:
                # Tạo query mới với synonym
                expanded = text_lower.replace(term, synonym)
                if expanded != text_lower and expanded not in expanded_queries:
                    expanded_queries.append(expanded)
                
                # Thêm query với cả term và synonym
                expanded_with_both = text_lower + " " + synonym
                if expanded_with_both not in expanded_queries:
                    expanded_queries.append(expanded_with_both)
    
    # Thêm query tiếng Việt nếu query là tiếng Anh và ngược lại
    has_vietnamese = any(char in text for char in 'áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ')
    
    if has_vietnamese:
        # Simple Vietnamese to English mapping
        vi_en_map = {
            'kiểm toán': 'audit',
            'chứng nhận': 'certification',
            'halal': 'halal',
            'yêu cầu': 'requirements',
            'tiêu chuẩn': 'standards',
            'là gì': 'what is',
            'đánh giá': 'assessment',
            'thanh tra': 'inspection',
            'quy trình': 'procedure',
            'tài liệu': 'documentation',
        }
        
        english_version = text_lower
        for vi, en in vi_en_map.items():
            if vi in english_version:
                english_version = english_version.replace(vi, en)
        
        if english_version != text_lower and english_version not in expanded_queries:
            expanded_queries.append(english_version)
    
    return expanded_queries[:5]  # Giới hạn 5 expanded queries

def enhance_query_for_retrieval(text: str) -> Dict[str, Any]:
    """Xử lý query để tối ưu retrieval."""
    query_type = classify_query_type(text)
    
    # Tạo search strategies dựa trên query type
    strategies = {
        "definition": {
            "boost_title": 1.5,  # Ưu tiên title chunks cho definition
            "min_score": 0.05,
            "require_exact_match": False
        },
        "procedure": {
            "boost_title": 1.2,
            "min_score": 0.08,
            "require_exact_match": True  # Cần exact match cho procedure
        },
        "requirement": {
            "boost_title": 1.3,
            "min_score": 0.07,
            "require_exact_match": True
        },
        "general": {
            "boost_title": 1.0,
            "min_score": 0.08,
            "require_exact_match": False
        }
    }
    
    strategy = strategies.get(query_type, strategies["general"])
    
    # Tạo expanded queries
    expanded_queries = expand_query_with_synonyms(text)
    
    return {
        "original": text,
        "type": query_type,
        "expanded": expanded_queries,
        "strategy": strategy
    }

def embed_query(text):
    encoder = get_encoder()
    
    # Enhanced query processing
    enhanced = enhance_query_for_retrieval(text)
    log.info(f"Query type: {enhanced['type']}, Expanded: {len(enhanced['expanded'])} versions")
    
    # Sử dụng bản gốc cho embedding, expansions sẽ dùng cho hybrid search
    text_to_embed = enhanced["original"]
    
    # Format query cho E5 model
    formatted_query = f"query: {text_to_embed}"
    
    return {
        "vector": encoder.encode(formatted_query, normalize_embeddings=True).tolist(),
        "enhanced": enhanced
    }

def format_source(payload):
    parts = [payload.get("source_file", "")]
    if payload.get("slide_num"):
        parts.append(f"Slide {payload['slide_num']}")
    if payload.get("slide_title"):
        parts.append(f"\"{payload['slide_title']}\"")
    return " · ".join(parts)

def hybrid_search(query_data, top_k=TOP_K, topic_filter=None):
    """Hybrid search kết hợp vector search và keyword matching."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
    client = QdrantClient(url=QDRANT_URL)
    
    query_vector = query_data["vector"]
    enhanced = query_data["enhanced"]
    original_query = enhanced["original"]
    strategy = enhanced["strategy"]
    
    all_points = []
    seen_ids = set()
    
    # PHASE 1: Exact keyword matching (cho các queries expanded)
    for expanded_query in enhanced["expanded"]:
        try:
            # Tìm exact match trong slide_title
            title_filter = Filter(
                must=[FieldCondition(key="slide_title", match=MatchText(text=expanded_query))]
            )
            
            title_results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=2,
                with_payload=True,
                query_filter=title_filter,
                score_threshold=0.01,
            ).points
            
            for point in title_results:
                if point.id not in seen_ids:
                    point.boosted_score = point.score * strategy["boost_title"]
                    all_points.append(point)
                    seen_ids.add(point.id)
            
            # Tìm exact match trong text
            text_filter = Filter(
                must=[FieldCondition(key="text", match=MatchText(text=expanded_query))]
            )
            
            text_results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=3,
                with_payload=True,
                query_filter=text_filter,
                score_threshold=0.01,
            ).points
            
            for point in text_results:
                if point.id not in seen_ids:
                    all_points.append(point)
                    seen_ids.add(point.id)
                    
        except Exception as e:
            log.debug(f"Keyword search failed for '{expanded_query}': {e}")
    
    # PHASE 2: Vector similarity search
    query_filter = None
    if topic_filter:
        query_filter = Filter(must=[FieldCondition(key="topics", match=MatchValue(value=topic_filter))])
    
    vector_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k * 3,
        with_payload=True,
        query_filter=query_filter,
        score_threshold=strategy["min_score"],
    ).points
    
    # Thêm vector results (chưa có trong all_points)
    for point in vector_results:
        if point.id not in seen_ids and len(all_points) < top_k * 4:
            all_points.append(point)
            seen_ids.add(point.id)
    
    # PHASE 3: Re-ranking với semantic và keyword boosting
    reranked_points = []
    
    for point in all_points:
        text = point.payload.get('text', '').lower()
        slide_title = point.payload.get('slide_title', '').lower()
        original_score = point.score
        
        # Base score
        final_score = original_score
        
        # Boost cho exact matches trong expanded queries
        for expanded_query in enhanced["expanded"]:
            exp_lower = expanded_query.lower()
            
            # Exact match trong title (cao nhất)
            if exp_lower in slide_title:
                final_score += 0.4
                break
            
            # Exact match trong text
            if exp_lower in text:
                final_score += 0.2
                break
        
        # Boost cho query type specific
        if enhanced["type"] == "definition" and "title" in text.lower():
            final_score += 0.15
        
        # Boost cho slide number (ưu tiên slide đầu)
        slide_num = point.payload.get('slide_num', 100)
        if slide_num <= 20:  # Ưu tiên slide đầu (thường là definitions)
            final_score += 0.1 * (1.0 - slide_num/100)
        
        reranked_points.append((final_score, point))
    
    # Sort by final score
    reranked_points.sort(key=lambda x: x[0], reverse=True)
    
    # PHASE 4: Diversity filtering (tránh trùng lặp)
    final_points = []
    seen_texts = set()
    
    for score, point in reranked_points:
        if len(final_points) >= top_k:
            break
            
        text = point.payload.get('text', '')[:200]  # Lấy 200 ký tự đầu để so sánh
        if text in seen_texts:
            continue
            
        seen_texts.add(text)
        final_points.append((score, point))
    
    # Convert to result format
    results = []
    for score, point in final_points[:RERANK_TOP_K]:
        results.append({
            "score": round(score, 3),
            "text": point.payload.get("text", ""),
            "payload": point.payload,
            "source": format_source(point.payload),
            "slide_num": point.payload.get("slide_num"),
            "slide_title": point.payload.get("slide_title", "")
        })
    
    log.info(f"Hybrid search: {len(results)} results after re-ranking")
    return results

def build_context(hits, max_words=2000):
    blocks, total = [], 0
    for i, h in enumerate(hits, 1):
        w = len(h["text"].split())
        if total + w > max_words:
            break
        blocks.append(f"[{i}] {h['source']}\n{h['text']}")
        total += w
    return "\n\n---\n\n".join(blocks)

def call_llm(prompt_text, original_question=None, context=None):
    """
    Dispatch to appropriate LLM backend based on LLM_BACKEND env variable.
    
    Backends in priority order:
    1. openrouter (recommended) - multiple models, reliable
    2. deepseek (fallback) - direct API
    3. [removed] ollama - external APIs only
    """
    
    if LLM_BACKEND == "openrouter":
        log.info(f"🔄 Using OpenRouter ({OPENROUTER_MODEL})")
        return call_openrouter(prompt_text, original_question, context)
    elif LLM_BACKEND == "deepseek":
        log.info(f"🔄 Using DeepSeek ({LLM_MODEL})")
        return call_deepseek(prompt_text, original_question, context)
    
    else:
        log.warning(f"Unknown LLM_BACKEND '{LLM_BACKEND}' - defaulting to OpenRouter")
        return call_openrouter(prompt_text, original_question, context)

def call_openrouter(prompt_text, original_question=None, context=None):
    """Goi OpenRouter API với multi-model support."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    if not OPENROUTER_API_KEY:
        log.error("OPENROUTER_API_KEY khong duoc cau hinh!")
        return call_deepseek(prompt_text, original_question, context)  # Fallback
    
    # Setup session with retry
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://aminra.ai",
        "X-Title": "Aminra Halal Certification AI",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT[:1000]},
            {"role": "user", "content": prompt_text[:6000]}
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "stream": False
    }
    
    try:
        response = session.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            raise ValueError("OpenRouter API returned no choices")
        
        answer = data["choices"][0]["message"]["content"].strip()
        log.info(f"✅ OpenRouter ({OPENROUTER_MODEL}): {len(answer)} chars")
        return answer
        
    except requests.exceptions.Timeout:
        log.error(f"⏱️ OpenRouter timeout - fallback to DeepSeek")
        return call_deepseek(prompt_text, original_question, context)
    except requests.exceptions.RequestException as e:
        log.error(f"❌ OpenRouter error ({e}) - fallback to DeepSeek")
        return call_deepseek(prompt_text, original_question, context)
    except Exception as e:
        log.error(f"❌ OpenRouter exception ({e}) - fallback to DeepSeek")
        return call_deepseek(prompt_text, original_question, context)

def call_deepseek(prompt_text, original_question=None, context=None):
    """Goi DeepSeek API với improved error handling."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY chua duoc cau hinh trong .env")
    
    # Setup session with retry
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT[:1000]},  # Limit system prompt
            {"role": "user", "content": prompt_text[:6000]}  # Limit user prompt
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "stream": False
    }
    
    try:
        response = session.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30  # Tăng timeout lên 30s
        )
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            raise ValueError("DeepSeek API returned no choices")
        
        return data["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        log.error("DeepSeek API timeout")
        # Fallback: Trả về kết quả dựa trên context nếu có
        if context and original_question:
            return _generate_fallback_answer(context, original_question)
        return "Xin lỗi, hệ thống đang xử lý quá lâu. Vui lòng thử lại với câu hỏi ngắn hơn."
    except requests.exceptions.RequestException as e:
        log.error(f"DeepSeek API error: {e}")
        # Fallback cho lỗi mạng
        question_text = original_question if original_question else "câu hỏi của bạn"
        return f"""**Thông báo hệ thống:**

Xin lỗi, không thể kết nối đến dịch vụ xử lý ngôn ngữ. 

Câu hỏi của bạn: "{question_text}"

**Khuyến nghị:**
1. Thử lại sau 1-2 phút
2. Kiểm tra kết nối mạng
3. Sử dụng câu hỏi ngắn hơn, cụ thể hơn

*Hệ thống vẫn có thể tìm kiếm thông tin nhưng không thể tạo câu trả lời tự nhiên.*"""
    except Exception as e:
        log.error(f"Unexpected error in call_deepseek: {e}")
        return "Có lỗi xảy ra khi xử lý câu trả lời. Vui lòng thử lại."

def _generate_fallback_answer(context, question):
    """Tạo answer fallback khi LLM API fails."""
    # Phân tích context để tạo structured response
    chunks = context.split("\n---\n")
    
    # Extract key information
    sources = []
    key_points = []
    
    for chunk in chunks[:4]:  # Lấy 4 chunks đầu
        lines = chunk.split('\n')
        if len(lines) >= 2:
            # Extract source
            source_line = lines[0]
            if 'Slide' in source_line:
                sources.append(source_line)
            
            # Extract content
            content = ' '.join(lines[1:])[:300]
            if content:
                key_points.append(f"• {content}...")
    
    # Tạo structured response
    response = f"""**Dựa trên tài liệu có sẵn:**

**Câu hỏi:** {question}

**Thông tin liên quan từ tài liệu:**

{chr(10).join(key_points[:5])}

**Nguồn tham khảo:**
{chr(10).join([f"- {src}" for src in sources[:3]])}

*Lưu ý: Hệ thống đang ở chế độ fallback. Câu trả lời được tổng hợp tự động từ các đoạn văn bản phù hợp nhất.*"""
    
    return response



@dataclass
class RAGResult:
    question:    str
    answer:      str
    sources:     list
    scores:      list
    chunks_used: int

class HalalRAG:
    """
    Interface chinh de query RAG pipeline.

    Vi du:
        rag = HalalRAG()
        result = rag.ask("Audit checklist la gi?")
        print(result.answer)
        print(result.sources)
    """

    def ask(self, question, top_k=TOP_K, topic_filter=None, lang=None):
        log.info(f"Question: {question[:80]}")

        # 1. Enhanced embedding và query processing
        query_data = embed_query(question)
        
        # 2. Hybrid search với re-ranking
        hits = hybrid_search(query_data, top_k=top_k, topic_filter=topic_filter)
        log.info(f"Found {len(hits)} chunks after hybrid search")

        if not hits:
            return RAGResult(
                question=question,
                answer=f"Không tìm thấy thông tin về '{question}' trong tài liệu hiện có.",
                sources=[], scores=[], chunks_used=0
            )

        # 3. Build context với chunk prioritization
        context = build_context(hits)

        # 4. Enhanced prompt với query type awareness
        query_type = query_data["enhanced"]["type"]
        
        prompt = f"""{build_system_prompt(lang)}

CONTEXT:
{context}

CÂU HỎI: {question}"""

        # 5. Goi LLM với multi-level fallback
        try:
            # Thử import local_llm module
            # Use new unified call_llm function
            answer = call_llm(prompt, original_question=question, context=context)
        except Exception as e:
            log.error(f"LLM with fallback failed: {e}")
            answer = _generate_fallback_answer(context, question)

        return RAGResult(
            question=question,
            answer=answer,
            sources=[h["source"] for h in hits],
            scores=[h["score"] for h in hits],
            chunks_used=len(hits),
        )
    
    def _get_query_type_guidance(self, query_type):
        """Trả về hướng dẫn cụ thể cho từng loại query."""
        guidance = {
            "definition": "Trả lời cần bao gồm: 1) Định nghĩa ngắn gọn, 2) Đặc điểm chính, 3) Ví dụ minh họa (nếu có).",
            "procedure": "Trả lời cần bao gồm: 1) Các bước thực hiện theo thứ tự, 2) Yêu cầu cho từng bước, 3) Lưu ý quan trọng.",
            "requirement": "Trả lời cần bao gồm: 1) Danh sách các yêu cầu chính, 2) Mức độ quan trọng, 3) Tiêu chí đánh giá.",
            "general": "Trả lời cần rõ ràng, có cấu trúc, tập trung vào thông tin quan trọng nhất."
        }
        return guidance.get(query_type, guidance["general"])

    def ask_stream(self, question, top_k=TOP_K, lang=None):
        """Generator: yield tung token (cho streaming UI)."""
        query_data = embed_query(question)
        hits = hybrid_search(query_data, top_k=top_k)
        context = build_context(hits)
        prompt = f"{build_system_prompt(lang)}\n\nCONTEXT:\n{context}\n\nCÂU HỎI: {question}"
        # Streaming via OpenRouter (primary) → DeepSeek (fallback)
        import requests
        api_key = OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY")
        base_url = OPENROUTER_BASE_URL if OPENROUTER_API_KEY else LLM_BASE_URL
        model    = OPENROUTER_MODEL    if OPENROUTER_API_KEY else LLM_MODEL

        if not api_key:
            yield "Loi: Chua cau hinh API key (OPENROUTER hoac DEEPSEEK)"
            return

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if OPENROUTER_API_KEY:
            headers["HTTP-Referer"] = "https://fe.silvergem.org"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
            "stream": True,
        }

        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            if 'choices' in json_data and json_data['choices']:
                                delta = json_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            log.error(f"Streaming error: {e}")
            yield f"Loi ket noi: {str(e)}"


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Halal audit la gi?"
    rag = HalalRAG()
    result = rag.ask(question)
    print("\n" + "=" * 60)
    print(f"CAU HOI: {result.question}")
    print("=" * 60)
    print(f"\n{result.answer}")
    print("\n" + "-" * 60)
    print(f"So chunks dung: {result.chunks_used}")
    print("Nguon:")
    for src, sc in zip(result.sources, result.scores):
        print(f"  [{sc}] {src}")