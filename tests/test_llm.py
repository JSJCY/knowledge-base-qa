import httpx
import pytest

from app.services.llm import DeepSeekLLMService, LLMError, MockLLMService


def _service_with(handler, api_key="sk-test") -> DeepSeekLLMService:
    return DeepSeekLLMService(
        api_key=api_key,
        base_url="https://example.invalid/v1",
        model="deepseek-chat",
        timeout=5.0,
        temperature=0.3,
        transport=httpx.MockTransport(handler),
    )


def test_deepseek_parses_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好"}}]})

    svc = _service_with(handler)
    assert svc.chat([{"role": "user", "content": "hi"}]) == "你好"


def test_deepseek_sends_auth_and_payload():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _service_with(handler).chat([{"role": "user", "content": "问题"}])
    assert seen["auth"] == "Bearer sk-test"
    assert "deepseek-chat" in seen["body"]
    assert "问题" in seen["body"]


def test_deepseek_raises_on_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    with pytest.raises(LLMError, match="401"):
        _service_with(handler).chat([{"role": "user", "content": "hi"}])


def test_deepseek_raises_on_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(LLMError, match="格式异常"):
        _service_with(handler).chat([{"role": "user", "content": "hi"}])


def test_mock_llm_echoes_question():
    out = MockLLMService().chat([{"role": "user", "content": "什么是RAG"}])
    assert "什么是RAG" in out
    assert "Mock" in out
