"""Smoke test chứng minh new test stack hoạt động.

Covers:
- pytest-asyncio (async def test_)
- respx (mock httpx call)
- pytest-mock (mocker fixture)
- parametrize (boundary values)

Chạy: docker exec aminra-docker-system-aminra-backend-1 pytest tests/test_example_new_stack.py -v
"""
import httpx
import pytest
import respx


# ── 1. pytest-asyncio — async test function ─────────────────────────────────
async def test_async_httpx_client_basic():
    """Prove pytest-asyncio auto-mode picks up async def without marker."""
    async with httpx.AsyncClient() as client:
        assert client is not None


# ── 2. respx — mock external HTTP call (LLM API) ────────────────────────────
@respx.mock
async def test_respx_mocks_openrouter_like_llm_call():
    """Pattern for mocking OpenRouter/DeepSeek in RAG tests."""
    fake_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "Halal là được phép theo Shariah."}}
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={"model": "deepseek/deepseek-chat", "messages": []},
        )

    assert r.status_code == 200
    assert fake_route.called
    assert "Halal" in r.json()["choices"][0]["message"]["content"]


# ── 3. pytest-mock — mocker fixture for unit-level mocking ──────────────────
def test_mocker_fixture_replaces_function(mocker):
    """pytest-mock wraps unittest.mock với scope tự động cleanup."""
    mock_fn = mocker.Mock(return_value=42)
    assert mock_fn("anything") == 42
    mock_fn.assert_called_once_with("anything")


# ── 4. parametrize — boundary values in 1 test ──────────────────────────────
@pytest.mark.parametrize(
    "status_code,expected_ok",
    [
        (200, True),
        (201, True),
        (204, True),
        (400, False),
        (401, False),
        (500, False),
    ],
)
def test_parametrize_http_status_classification(status_code: int, expected_ok: bool):
    """1 function, 6 test cases — pattern cho test boundary values."""
    assert (200 <= status_code < 300) == expected_ok
