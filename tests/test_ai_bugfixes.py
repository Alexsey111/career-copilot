# tests/test_ai_bugfixes.py

"""Этап 2.1 — regression-тесты багфиксов AI-подсистемы.

Покрывает:
- PROMPT_REGISTRY integrity: каждый используемый use_cases-ами шаблон
  зарегистрирован; мёртвых enum-членов (без регистрации и без использования)
  нет.
- tracing.trace_ai_run принимает provider_name и используется оркестратором
  (не мёртвый код).
- create_ai_orchestrator строит оркестратор через штатный конструктор.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.ai.factory import create_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PROMPT_REGISTRY, PromptTemplate
from app.ai.tracing import trace_ai_run
from app.core.config import get_settings


# Шаблоны, фактически используемые use_cases (resume_tailoring, resume_enhance,
# cover_letter_enhance, interview_coach).
_USED_TEMPLATES = {
    PromptTemplate.RESUME_TAILOR_V1,
    PromptTemplate.RESUME_ENHANCE_V1,
    PromptTemplate.COVER_LETTER_ENHANCE_V1,
    PromptTemplate.INTERVIEW_COACH_V1,
    PromptTemplate.INTERVIEW_COACH_ADVISORY_V1,
    PromptTemplate.INTERVIEW_COACHING_V1,
}

# Enum-члены, используемые только как строковые label (generation_prompt_version)
# без LLM-вызова через orchestrator — регистрировать их в PROMPT_REGISTRY не нужно.
_LABEL_ONLY_TEMPLATES = {
    PromptTemplate.COVER_LETTER_V1,
    PromptTemplate.COVER_LETTER_GAP_MITIGATION,
}


def test_used_prompt_templates_are_registered():
    for template in _USED_TEMPLATES:
        assert template in PROMPT_REGISTRY, (
            f"Used template {template} is missing from PROMPT_REGISTRY"
        )


def test_no_dead_prompt_enum_members():
    """Каждый enum-член либо зарегистрирован, либо является известным label."""
    for member in PromptTemplate:
        assert member in PROMPT_REGISTRY or member in _LABEL_ONLY_TEMPLATES, (
            f"Dead PromptTemplate member without registry entry or label use: {member}"
        )


@pytest.mark.asyncio
async def test_trace_ai_run_forwards_provider_name():
    """trace_ai_run должен передавать provider_name в репозиторий (не мёртвый)."""
    repo = AsyncMock()
    with patch(
        "app.repositories.ai_run_repository.AIRunRepository",
        return_value=repo,
    ):
        await trace_ai_run(
            session=AsyncMock(),
            run_id=uuid4(),
            user_id=uuid4(),
            workflow_name="test",
            target_type="vacancy",
            target_id=None,
            provider_name="gigachat",
            model_name="gigachat-pro",
            prompt_version="resume_tailor_v1",
            input_snapshot={},
            output_snapshot={"a": 1},
            duration_ms=10,
            tokens_used={"prompt_tokens": 1},
        )

    repo.create_success.assert_awaited_once()
    kwargs = repo.create_success.call_args.kwargs
    assert kwargs["provider_name"] == "gigachat"
    assert kwargs["output_snapshot"] == {"a": 1}


@pytest.mark.asyncio
async def test_create_ai_orchestrator_wires_config_from_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_DEFAULT_MODEL", "test-model")
    monkeypatch.delenv("AI_FALLBACK_PROVIDER", raising=False)
    get_settings.cache_clear()

    try:
        orchestrator = create_ai_orchestrator()
        assert isinstance(orchestrator, AIOrchestrator)
        assert orchestrator.client is not None
        # from_settings пробрасывает AI_DEFAULT_MODEL в конфиг.
        assert orchestrator.config.default_model == "test-model"
        # ai_run_repo инициализирован (наблюдаемость).
        assert orchestrator.ai_run_repo is not None
        assert orchestrator.fallback_client is None
    finally:
        get_settings.cache_clear()