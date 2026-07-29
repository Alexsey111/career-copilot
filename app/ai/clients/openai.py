from __future__ import annotations

import json
from typing import Any

import httpx
from jsonschema import ValidationError, validate

from app.ai.clients.base import BaseLLMClient, LLMClientError, resolve_llm_verify
from app.core.config import get_settings


class OpenAILLMClient(BaseLLMClient):
    def __init__(self):
        settings = get_settings()

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")

        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.openai_timeout,
            verify=resolve_llm_verify(settings),
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    async def aclose(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _resolve_model(model: str | None) -> str:
        """Нормализация под OpenAI: None или не-gpt-модель → ``gpt-4o-mini``.
        Защита от чужой модели (``gigachat-pro``/``deepseek-chat``) при per-user
        override провайдера."""
        if model and str(model).strip().lower().startswith("gpt"):
            return str(model)
        return "gpt-4o-mini"

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        try:
            resolved_model = self._resolve_model(model)
            payload: dict[str, Any] = {
                "model": resolved_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature if temperature is not None else 0.1,
            }

            if max_tokens is not None:
                payload["max_tokens"] = max_tokens

            response = await self.client.post("/chat/completions", json=payload)

            if response.status_code == 401:
                raise LLMClientError(f"HTTP {response.status_code}: Unauthorized", retryable=False)
            if response.status_code == 400:
                raise LLMClientError(f"HTTP {response.status_code}: Bad Request", retryable=False)
            if response.status_code != 200:
                raise LLMClientError(f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            choice = data["choices"][0]
            return {
                "content": choice["message"]["content"],
                "usage": data.get("usage", {}),
                "model": data.get("model", resolved_model),
                "finish_reason": choice.get("finish_reason"),
            }
        except LLMClientError:
            raise
        except Exception as exc:
            raise LLMClientError(str(exc)) from exc

    async def generate_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        result = await self.generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            parsed = self._safe_parse_json(result["content"])
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"Invalid JSON: {exc}") from exc

        try:
            validate(instance=parsed, schema=output_schema)
        except ValidationError as exc:
            raise LLMClientError(f"Schema validation error: {exc.message}") from exc

        return {
            "content": parsed,
            "usage": result.get("usage", {}),
            "model": result.get("model"),
            "finish_reason": result.get("finish_reason"),
        }

    @staticmethod
    def _safe_parse_json(text: str) -> dict[str, Any]:
        text = text.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

        return json.loads(text)
