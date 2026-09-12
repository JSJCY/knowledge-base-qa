"""LLM 服务：DeepSeek Chat API 接入，未配置 Key 时自动降级 Mock。

- DeepSeekLLMService：标准 OpenAI 兼容 /chat/completions 调用；
- MockLLMService：无 Key 时的可插拔占位实现，保证全流程可跑通；
- 测试通过依赖注入替换，不产生真实调用。
"""

import json
from collections.abc import Iterator
from typing import Protocol

import httpx

from app.core.config import get_settings


class LLMError(RuntimeError):
    """LLM 调用失败（网络、鉴权、限流等）。"""


class LLMService(Protocol):
    mode: str

    def chat(self, messages: list[dict[str, str]]) -> str: ...

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]: ...


class MockLLMService:
    """未配置 DEEPSEEK_API_KEY 时的占位实现。"""

    mode = "mock"

    def chat(self, messages: list[dict[str, str]]) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        return (
            "【Mock 模式】未配置 DEEPSEEK_API_KEY，无法调用真实大模型。"
            f"已收到问题：{last_user[:100]}"
        )

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        answer = self.chat(messages)
        for i in range(0, len(answer), 12):
            yield answer[i : i + 12]


class DeepSeekLLMService:
    """DeepSeek（OpenAI 兼容）Chat Completions 客户端。"""

    mode = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        temperature: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def chat(self, messages: list[dict[str, str]]) -> str:
        try:
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "stream": False,
                },
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"请求 DeepSeek 失败：{exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"DeepSeek API 返回 {resp.status_code}：{resp.text[:200]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"DeepSeek 响应格式异常：{data}") from exc

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        try:
            with self._client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code != 200:
                    detail = resp.read().decode()[:200]
                    raise LLMError(f"DeepSeek API 返回 {resp.status_code}：{detail}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {}).get("content")
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        raise LLMError(f"DeepSeek 流式响应格式异常：{data[:200]}") from exc
                    if delta:
                        yield delta
        except httpx.HTTPError as exc:
            raise LLMError(f"请求 DeepSeek 失败：{exc}") from exc


_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """FastAPI 依赖入口（进程内单例，测试可 override）。"""
    global _llm_service
    if _llm_service is None:
        settings = get_settings()
        if settings.llm_enabled:
            _llm_service = DeepSeekLLMService(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                timeout=settings.llm_timeout_seconds,
                temperature=settings.llm_temperature,
            )
        else:
            _llm_service = MockLLMService()
    return _llm_service
