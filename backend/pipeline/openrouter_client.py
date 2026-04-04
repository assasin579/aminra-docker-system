"""
OpenRouter API Client with Multi-Model Support and Fallback
"""

import os
import requests
import logging
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("aminra.openrouter")

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model Configurations (in priority order)
MODELS = {
    "deepseek": {
        "id": "deepseek/deepseek-chat",
        "name": "DeepSeek Chat",
        "cost": "cheap",
        "speed": "fast"
    },
    "llama": {
        "id": "meta-llama/llama-2-70b-chat",
        "name": "Llama 2 70B",
        "cost": "cheap",
        "speed": "fast"
    },
    "mixtral": {
        "id": "mistralai/mixtral-8x7b",
        "name": "Mixtral 8x7B",
        "cost": "cheap",
        "speed": "fast"
    },
    "claude": {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "cost": "moderate",
        "speed": "fast"
    }
}

DEFAULT_MODEL = "deepseek"
FALLBACK_MODELS = ["llama", "mixtral", "claude"]

SYSTEM_PROMPT = """Bạn là Aminra - chuyên gia tư vấn chứng nhận Halal với 10 năm kinh nghiệm.

HƯỚNG DẪN TRẢ LỜI:
1. Dựa HOÀN TOÀN vào ngữ cảnh được cung cấp
2. Trả lời bằng tiếng Việt, trừ khi được yêu cầu khác
3. Cấu trúc câu trả lời:
   - Phần tóm tắt ngắn (1-2 câu)
   - Chi tiết chính (bullet points)
   - Ví dụ minh họa (nếu có)
   - Khuyến nghị thực tế
4. Luôn trích dẫn nguồn: [Tên file, Slide số]

ĐỘ CHÍNH XÁC:
- Nếu không có thông tin trong context: "Không tìm thấy thông tin về [chủ đề] trong tài liệu hiện có."
- Nếu thông tin mâu thuẫn: trình bày cả hai quan điểm với nguồn
- Ưu tiên thông tin từ slide gần đây nhất

TONALITY:
- Chuyên nghiệp nhưng thân thiện
- Rõ ràng, dễ hiểu
- Cung cấp giá trị thực tế cho doanh nghiệp"""


class OpenRouterClient:
    """OpenRouter API Client with multi-model support"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenRouter client"""
        self.api_key = api_key or OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured in .env")
        
        # Setup session with retry strategy
        self.session = self._create_session()
        self.current_model = DEFAULT_MODEL
        self.model_history = []
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
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
        return session
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://aminra.ai",
            "X-Title": "Aminra AI",
            "Content-Type": "application/json"
        }
    
    def call_model(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Call OpenRouter API with specified model"""
        
        model_key = model or self.current_model
        if model_key not in MODELS:
            log.warning(f"Model {model_key} not found, using {DEFAULT_MODEL}")
            model_key = DEFAULT_MODEL
        
        model_config = MODELS[model_key]
        model_id = model_config["id"]
        
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt[:6000]}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            log.info(f"Calling {model_config['name']} ({model_id})")
            
            response = self.session.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise ValueError("No choices in response")
            
            result = {
                "success": True,
                "model": model_config["name"],
                "model_id": model_id,
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {})
            }
            
            self.current_model = model_key
            self.model_history.append(model_key)
            
            log.info(f"✅ {model_config['name']} succeeded")
            return result
            
        except requests.exceptions.Timeout:
            log.error(f"❌ {model_config['name']} timeout")
            return {
                "success": False,
                "model": model_config["name"],
                "error": "timeout",
                "message": f"{model_config['name']} timed out"
            }
        except requests.exceptions.RequestException as e:
            log.error(f"❌ {model_config['name']} error: {e}")
            return {
                "success": False,
                "model": model_config["name"],
                "error": "request_error",
                "message": str(e)
            }
        except Exception as e:
            log.error(f"❌ Unexpected error with {model_config['name']}: {e}")
            return {
                "success": False,
                "model": model_config["name"],
                "error": "unexpected",
                "message": str(e)
            }
    
    def call_with_fallback(
        self,
        prompt: str,
        preferred_model: Optional[str] = None,
        fallback_models: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Call model with automatic fallback to other models"""
        
        # Determine model sequence
        models_to_try = [preferred_model or self.current_model] + (fallback_models or FALLBACK_MODELS)
        models_to_try = [m for m in models_to_try if m in MODELS]
        
        log.info(f"Trying models in order: {models_to_try}")
        
        last_error = None
        for model_key in models_to_try:
            result = self.call_model(prompt, model=model_key, **kwargs)
            
            if result["success"]:
                return result
            
            last_error = result
            log.warning(f"Model {model_key} failed: {result.get('message')}")
        
        # All models failed
        return {
            "success": False,
            "error": "all_models_failed",
            "message": "Tất cả các mô hình đều thất bại. Vui lòng thử lại sau.",
            "last_error": last_error
        }
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics about model usage"""
        return {
            "current_model": self.current_model,
            "models_available": list(MODELS.keys()),
            "model_history": self.model_history,
            "total_calls": len(self.model_history)
        }


def call_openrouter(
    prompt: str,
    original_question: Optional[str] = None,
    context: Optional[str] = None,
    preferred_model: Optional[str] = None,
    use_fallback: bool = True
) -> str:
    """
    Call OpenRouter API with automatic fallback
    
    Args:
        prompt: Full prompt with system + context + question
        original_question: Original question (for logging)
        context: Context/retrieval results
        preferred_model: Preferred model to use
        use_fallback: Whether to use fallback models
    
    Returns:
        Generated response text
    """
    
    try:
        client = OpenRouterClient()
        
        if use_fallback:
            result = client.call_with_fallback(
                prompt,
                preferred_model=preferred_model,
                fallback_models=FALLBACK_MODELS
            )
        else:
            result = client.call_model(prompt, model=preferred_model)
        
        if result["success"]:
            log.info(f"✅ Response generated by {result['model']}")
            return result["content"]
        else:
            log.error(f"❌ All models failed: {result['message']}")
            return generate_fallback_answer(context, original_question)
    
    except Exception as e:
        log.error(f"OpenRouter client error: {e}")
        return generate_fallback_answer(context, original_question)


def generate_fallback_answer(context: Optional[str], question: Optional[str]) -> str:
    """Generate answer when all LLMs fail"""
    
    if not context:
        return "Xin lỗi, hệ thống tạm thời không khả dụng. Vui lòng thử lại sau."
    
    return f"""**Thông báo hệ thống:**

Xin lỗi, không thể tạo câu trả lời tự động. Dưới đây là thông tin từ tài liệu:

{context}

**Khuyến nghị:**
1. Thử lại sau vài phút
2. Rephrase câu hỏi một cách cụ thể hơn
3. Liên hệ hỗ trợ nếu vấn đề tiếp tục"""
