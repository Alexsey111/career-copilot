from __future__ import annotations

from typing import Any

from app.ai.clients.base import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """Deterministic local/test LLM client.

    Used for tests, demos and provider-switching contract checks.
    Must not be enabled in production.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    async def aclose(self) -> None:
        return None

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return {
            "content": "mock response",
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "model": model or "mock-model",
            "finish_reason": "stop",
        }

    async def generate_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return {
            "content": self._default_structured_payload(output_schema),
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "model": model or "mock-model",
            "finish_reason": "stop",
        }

    def _default_structured_payload(self, output_schema: dict[str, Any]) -> dict[str, Any]:
        properties = output_schema.get("properties") or {}
        payload: dict[str, Any] = {}

        for key, spec in properties.items():
            value_type = spec.get("type")
            if value_type == "array":
                payload[key] = []
            elif value_type == "number":
                payload[key] = 0
            elif value_type == "integer":
                payload[key] = 0
            elif value_type == "boolean":
                payload[key] = False
            elif value_type == "object":
                payload[key] = {}
            else:
                payload[key] = "mock"

        return payload or {"result": "mock"}
