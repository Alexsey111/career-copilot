# app\api\ai\orchestrator.py

from __future__ import annotations

import asyncio
import random
import time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from .clients.base import BaseLLMClient, LLMClientError
from .config import AIOrchestratorConfig, AIModel
from .registry.prompts import PromptRenderingError, PromptSpec, PromptTemplate, get_prompt, safe_render_prompt
from .tracing import trace_ai_run
from app.repositories.ai_run_repository import AIRunRepository  # создадим ниже


class AIOrchestrator:
    """
    Ядро оркестрации AI-запросов:
    - retry с экспоненциальной задержкой
    - fallback на резервную модель
    - трассировка в БД (AI_RUNS)
    - cost tracking
    """
    
    def __init__(
        self,
        client: BaseLLMClient | None = None,
        config: AIOrchestratorConfig | None = None,
        fallback_client: BaseLLMClient | None = None,
    ):
        if client is None:
            from app.ai.clients.gigachat import GigaChatClient
            client = GigaChatClient()
        self.client = client
        self.config = config or AIOrchestratorConfig.from_settings()
        self.fallback_client = fallback_client
        self.ai_run_repo = AIRunRepository()
    
    @classmethod
    def from_settings(cls) -> "AIOrchestrator":
        """Фабричный метод: создаёт оркестратор с дефолтным GigaChat клиентом."""
        from app.ai.clients.gigachat import GigaChatClient

        client = GigaChatClient()
        return cls(client=client)
    
    async def aclose(self) -> None:
        """Закрывает все HTTP-клиенты."""
        await self.client.aclose()
        if self.fallback_client:
            await self.fallback_client.aclose()

    async def execute(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        prompt_template: PromptTemplate,
        prompt_vars: dict[str, Any],
        workflow_name: str,
        target_type: str,
        target_id: str | None = None,
        model_override: AIModel | str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Выполняет AI-запрос с полной обвязкой.
        
        Args:
            language: Язык ответа (default: "en")
        
        Returns:
            dict с ключами:
            - result: dict|str (распарсенный ответ)
            - usage: dict (токены)
            - cost: float (если настроено)
            - model: str (какая модель фактически использована)
        """
        # 1. Загружаем спецификацию промпта
        spec = get_prompt(prompt_template)
        
        # 2. Добавляем language только если промпт его ожидает
        prompt_vars_final = dict(prompt_vars)
        if "language" in spec.input_schema:
            prompt_vars_final["language"] = language

        # 2a. Валидация: все поля из input_schema должны быть заполнены
        for field in spec.input_schema.keys():
            if field not in prompt_vars_final:
                raise ValueError(f"Missing prompt var: {field}")

        # 3. Рендерим шаблон безопасно
        try:
            prompt = safe_render_prompt(spec.template, prompt_vars_final)
        except PromptRenderingError as e:
            raise LLMClientError(str(e)) from e
        
        # 3. Параметры запроса
        model = (
            model_override
            or spec.model_hint
            or self.config.default_model
        )
        temperature = spec.temperature_hint or self.config.temperature
        response_format = spec.output_schema
    
        # 4. ID трассировки
        run_id = uuid4()
        start_ts = time.time()
        
        try:
            try:
                # 5. Выполнение с ретраями (с глобальным timeout)
                async with asyncio.timeout(self.config.request_timeout_sec):
                    result = await self._execute_with_retry(
                        prompt=prompt,
                        model=model,
                        temperature=temperature,
                        response_format=response_format,
                    )
            except TimeoutError as e:
                raise LLMClientError(
                    f"Orchestrator timeout after {self.config.request_timeout_sec}s"
                ) from e

            duration_ms = int((time.time() - start_ts) * 1000)

            # 6. Трассировка успеха
            if self.config.enable_tracing:
                await self.ai_run_repo.create_success(
                    session,
                    run_id=run_id,
                    user_id=user_id,
                    workflow_name=workflow_name,
                    target_type=target_type,
                    target_id=target_id,
                    provider_name=self.client.provider_name,
                    model_name=model,
                    prompt_version=prompt_template.value,
                    input_snapshot=self._sanitize_snapshot(prompt_vars),
                    output_snapshot=self._sanitize_snapshot(result),
                    duration_ms=duration_ms,
                    tokens_used=result.get("usage", {}),
                )
                await session.commit()

            return {
                "result": result.get("content"),
                "usage": result.get("usage", {}),
                "cost": self._calc_cost(result.get("usage", {})),
                "model": model,
            }

        except LLMClientError as e:
            # 7. Трассировка ошибки
            duration_ms = int((time.time() - start_ts) * 1000)
            if self.config.enable_tracing:
                await self.ai_run_repo.create_error(
                    session,
                    run_id=run_id,
                    user_id=user_id,
                    workflow_name=workflow_name,
                    target_type=target_type,
                    target_id=target_id,
                    provider_name=self.client.provider_name,
                    model_name=model,
                    prompt_version=prompt_template.value,
                    input_snapshot=self._sanitize_snapshot(prompt_vars),
                    error_text=str(e),
                    duration_ms=duration_ms,
                )
                await session.commit()
            raise
    
    async def _execute_with_retry(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Выполнение с ретраями и fallback"""
        last_error: Exception | None = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if response_format:
                    return await self.client.generate_structured(
                        prompt=prompt,
                        output_schema=response_format,
                        model=model,
                        temperature=temperature,
                        max_tokens=self.config.max_tokens,
                    )
                else:
                    return await self.client.generate(
                        prompt=prompt,
                        model=model,
                        temperature=temperature,
                        max_tokens=self.config.max_tokens,
                    )
            except LLMClientError as e:
                last_error = e
                # Если ошибка не retryable (401, 400) — сразу прерываем
                if not e.retryable:
                    break
                if attempt < self.config.max_retries:
                    # Экспоненциальная задержка с jitter (±20%)
                    await asyncio.sleep(
                        self.config.retry_backoff_sec * (2 ** attempt) * random.uniform(0.8, 1.2)
                    )
                    continue
                # Если есть fallback-клиент — пробуем его
                elif self.fallback_client:
                    try:
                        if response_format:
                            return await self.fallback_client.generate_structured(
                                prompt=prompt,
                                output_schema=response_format,
                                model=model,
                                temperature=temperature,
                                max_tokens=self.config.max_tokens,
                            )
                        else:
                            return await self.fallback_client.generate(
                                prompt=prompt,
                                model=model,
                                temperature=temperature,
                                max_tokens=self.config.max_tokens,
                            )
                    except LLMClientError:
                        pass  # продолжаем к выбросу
                break
        
        raise LLMClientError(
            f"Failed after {self.config.max_retries + 1} attempts: {last_error}"
        )

    def _calc_cost(self, usage: dict[str, int]) -> float:
        """Расчёт стоимости запроса (если настроено)"""
        if not self.config.cost_per_1k_tokens_input:
            return 0.0
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return (
            input_tokens * self.config.cost_per_1k_tokens_input / 1000 +
            output_tokens * self.config.cost_per_1k_tokens_output / 1000
        )

    @staticmethod
    def _sanitize_snapshot(data: dict[str, Any]) -> dict[str, Any]:
        """Ограничивает длину строковых значений в snapshot для трассировки.

        Применяется к input_snapshot и output_snapshot.
        Предотвращает:
        - переполнение БД большими payloads
        - утечку PII через необрезанные строки
        """
        MAX_LEN = 2000

        def sanitize(value: Any) -> Any:
            if isinstance(value, str):
                return value[:MAX_LEN]
            if isinstance(value, list):
                return [sanitize(v) for v in value]
            if isinstance(value, dict):
                return {k: sanitize(v) for k, v in value.items()}
            return value

        return sanitize(data)