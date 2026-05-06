# app\api\ai\clients\gigachat.py

from __future__ import annotations

import httpx
import json
from typing import Any

from jsonschema import validate, ValidationError

from app.core.config import get_settings

from .base import BaseLLMClient, LLMClientError


class GigaChatClient(BaseLLMClient):
    def __init__(self):
        settings = get_settings()

        if not settings.gigachat_api_key:
            raise ValueError("GIGACHAT_API_KEY is not set")

        self.base_url = settings.gigachat_base_url or "https://gigachat.devices.sberbank.ru/api/v1"
        self.api_key = settings.gigachat_api_key

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.ai_request_timeout,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    @property
    def provider_name(self) -> str:
        return "gigachat"

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature or 0.1,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            resp = await self.client.post("/chat/completions", json=payload)

            if resp.status_code != 200:
                raise LLMClientError(f"HTTP {resp.status_code}: {resp.text}")

            data = resp.json()

            content = data["choices"][0]["message"]["content"]

            return {
                "content": content,
                "usage": data.get("usage", {}),
                "model": data.get("model", model),
                "finish_reason": data["choices"][0].get("finish_reason"),
            }

        except Exception as e:
            raise LLMClientError(str(e)) from e

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

        raw_content = result["content"]

        try:
            parsed = self._safe_parse_json(raw_content)
        except json.JSONDecodeError as e:
            raise LLMClientError(f"Invalid JSON: {e}")

        try:
            validate(instance=parsed, schema=output_schema)
        except ValidationError as e:
            raise LLMClientError(f"Schema validation error: {e.message}")

        return {
            "content": parsed,
            "usage": result.get("usage", {}),
            "model": result.get("model"),
        }

    @staticmethod
    def _safe_parse_json(text: str) -> dict[str, Any]:
        """Безопасно парсит JSON, убирая markdown-обёртку и лишние префиксы."""
        text = text.strip()

        # Убираем markdown-обёртку ```json ... ```
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Убираем префикс "json" после открывающих тройных кавычек
        if text.lower().startswith("json"):
            text = text[4:].strip()

        return json.loads(text)

    @staticmethod
    def _extract_json_from_text(text: str) -> str:
        """Извлекает JSON из текста, убирая markdown-обёртку."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text