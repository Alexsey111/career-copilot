from __future__ import annotations

import json
from typing import Any

import httpx
from jsonschema import ValidationError, validate

from app.ai.clients.base import BaseLLMClient, LLMClientError, resolve_llm_verify
from app.core.config import get_settings


class DeepSeekLLMClient(BaseLLMClient):
    """DeepSeek-клиент (NLG-слой поверх детерминированной логики).

    DeepSeek API совместим с OpenAI Chat Completions (POST /chat/completions,
    Bearer auth, JSON, поле ``usage`` в ответе). Это drop-in замена
    ``OpenAILLMClient`` с другими ``base_url`` и ``api_key``. Используется
    когда ``Subscription.ai_provider == "deepseek"``.

    Per skill: модель НЕ выбирается пользователем — она фиксирована в коде
    (deepseek-chat). Провайдер может быть openai/deepseek/gigachat (через
    Subscription.ai_provider); дефолт — ``settings.ai_provider``.
    """

    def __init__(self):
        settings = get_settings()

        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.api_key = settings.deepseek_api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.deepseek_timeout,
            verify=resolve_llm_verify(settings),
        )

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def aclose(self) -> None:
        await self.client.aclose()

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = {
                "model": model,
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
                "model": data.get("model", model),
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
