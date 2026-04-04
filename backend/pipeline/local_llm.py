#!/usr/bin/env python3
"""
Local LLM integration với Ollama.
"""

import requests
import logging
import os
from typing import Optional

log = logging.getLogger("aminra.llm")

def call_ollama(prompt: str, model: str = "qwen2.5:3b", timeout: int = 60) -> str:
    """
    Gọi Ollama local LLM.
    
    Args:
        prompt: Prompt text
        model: Ollama model name (default: qwen2.5:3b)
        timeout: Timeout in seconds
    
    Returns:
        Generated text
    """
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 1500
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        if "response" not in data:
            raise ValueError(f"Ollama response missing 'response' field: {data}")
        
        return data["response"]
        
    except requests.exceptions.ConnectionError:
        log.error("Ollama not running on localhost:11434")
        raise
    except requests.exceptions.Timeout:
        log.error(f"Ollama timeout after {timeout}s")
        raise
    except Exception as e:
        log.error(f"Ollama error: {e}")
        raise

def call_llm_with_fallback(prompt: str, original_question: str, context: str) -> str:
    """
    Try DeepSeek API first, fallback to Ollama, then to simple fallback.
    """
    # Priority 1: DeepSeek API
    try:
        from .query import call_deepseek
        return call_deepseek(prompt, original_question, context)
    except Exception as e:
        log.warning(f"DeepSeek failed: {e}")
    
    # Priority 2: Ollama local
    try:
        return call_ollama(prompt, timeout=30)
    except Exception as e:
        log.warning(f"Ollama failed: {e}")
    
    # Priority 3: Simple fallback
    from .query import _generate_fallback_answer
    return _generate_fallback_answer(context, original_question)

def check_ollama_available() -> bool:
    """Kiểm tra Ollama có đang chạy không."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

def get_available_models() -> list:
    """Lấy danh sách models có sẵn trong Ollama."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
    except:
        pass
    return []

if __name__ == "__main__":
    # Test Ollama
    print("Testing Ollama integration...")
    
    if check_ollama_available():
        print("✅ Ollama is running")
        models = get_available_models()
        print(f"Available models: {models}")
        
        # Test với prompt đơn giản
        test_prompt = "Xin chào, bạn là ai?"
        try:
            response = call_ollama(test_prompt, timeout=10)
            print(f"\nTest response: {response[:100]}...")
        except Exception as e:
            print(f"❌ Ollama test failed: {e}")
    else:
        print("❌ Ollama not running. Install with: curl -fsSL https://ollama.ai/install.sh | sh")
        print("Then run: ollama pull qwen2.5:3b")