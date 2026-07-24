"""Тесты ``DeepSeekLLMClient`` (#37 DeepSeek).

Клиент — drop-in совместимый с OpenAI Chat Completions: тот же payload shape,
тот же response. Моки через ``httpx.MockTransport`` (respx/httpx_mock не
в списке зависимостей). Ключевая цель — зафиксировать контракт с
внешним API, чтобы регрессии (401 vs 429, JSON shape, Bearer auth)
ловились сразу.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.ai.clients.base import LLMClientError
from app.ai.clients.deepseek import DeepSeekLLMClient


def _build_client(transport: httpx.MockTransport) -> DeepSeekLLMClient:
    """Создаёт клиент с подменённым HTTP-транспортом (минуя ``get_settings``)."""
    client = DeepSeekLLMClient.__new__(DeepSeekLLMClient)
    client.base_url = "https://api.deepseek.com/v1"
    client.api_key = "test-key"
    client.client = httpx.AsyncClient(
        base_url=client.base_url,
        headers={
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        },
        transport=transport,
    )
    return client


@pytest.mark.asyncio
async def test_generate_posts_to_chat_completions_with_bearer():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Привет"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
        )

    client = _build_client(httpx.MockTransport(handler))
    try:
        result = await client.generate(
            "Сделай summary",
            model="deepseek-chat",
            temperature=0.2,
        )
    finally:
        await client.aclose()

    assert captured["path"] == "/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"] == [
        {"role": "user", "content": "Сделай summary"}
    ]
    assert captured["body"]["temperature"] == 0.2
    assert result["content"] == "Привет"
    assert result["model"] == "deepseek-chat"
    assert result["usage"]["total_tokens"] == 8
    assert result["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_generate_uses_default_temperature_when_none():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "model": "deepseek-chat",
                "usage": {},
            },
        )

    client = _build_client(httpx.MockTransport(handler))
    try:
        await client.generate("hi", model="deepseek-chat")
    finally:
        await client.aclose()

    # default temperature — 0.1 (детерминированная логика требует стабильности).
    assert seen["body"]["temperature"] == 0.1


@pytest.mark.asyncio
async def test_generate_401_raises_non_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_api_key"})

    client = _build_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMClientError) as exc_info:
            await client.generate("hi", model="deepseek-chat")
    finally:
        await client.aclose()

    assert exc_info.value.retryable is False
    assert "401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_400_raises_non_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad_request"})

    client = _build_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMClientError) as exc_info:
            await client.generate("hi", model="deepseek-chat")
    finally:
        await client.aclose()

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_generate_500_raises_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = _build_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMClientError) as exc_info:
            await client.generate("hi", model="deepseek-chat")
    finally:
        await client.aclose()

    # 500 — retryable по умолчанию (оркестратор сделает backoff).
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_generate_structured_parses_json_and_validates():
    def handler(request: httpx.Request) -> httpx.Response:
        # LLM вернул markdown-обёртку — клиент должен снять ```json ... ```.
        content = "```json\n{\"name\": \"Alice\", \"age\": 30}\n```"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "model": "deepseek-chat",
                "usage": {"total_tokens": 10},
            },
        )

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    client = _build_client(httpx.MockTransport(handler))
    try:
        result = await client.generate_structured(
            "extract",
            schema,
            model="deepseek-chat",
        )
    finally:
        await client.aclose()

    assert result["content"] == {"name": "Alice", "age": 30}


@pytest.mark.asyncio
async def test_generate_structured_schema_validation_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"name": "Alice"}'},
                        "finish_reason": "stop",
                    }
                ],
                "model": "deepseek-chat",
                "usage": {},
            },
        )

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    client = _build_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMClientError, match="Schema validation"):
            await client.generate_structured("extract", schema, model="deepseek-chat")
    finally:
        await client.aclose()


def test_provider_name_is_deepseek():
    client = DeepSeekLLMClient.__new__(DeepSeekLLMClient)
    assert client.provider_name == "deepseek"
