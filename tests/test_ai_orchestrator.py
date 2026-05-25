from __future__ import annotations

import pytest

from app.ai.clients.base import BaseLLMClient, LLMClientError
from app.ai.clients.mock import MockLLMClient
from app.ai.config import AIOrchestratorConfig
from app.ai.factory import create_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


class FailingLLMClient(BaseLLMClient):
    """Клиент, который всегда падает"""

    @property
    def provider_name(self):
        return "failing-mock"

    async def aclose(self):
        pass

    async def generate(self, *args, **kwargs):
        raise LLMClientError("Always fails")

    async def generate_structured(self, prompt, output_schema, **kwargs):
        raise LLMClientError("Always fails")


@pytest.mark.asyncio
async def test_orchestrator_executes_with_mock_client(db_session):
    """Проверяет, что orchestrator выполняет запрос через мок-клиент"""
    orchestrator = AIOrchestrator(
        client=MockLLMClient(),
        config=AIOrchestratorConfig(
            default_model="test-model",
            enable_tracing=False,
        ),
    )

    result = await orchestrator.execute(
        db_session,
        user_id="00000000-0000-0000-0000-000000000001",
        prompt_template=PromptTemplate.INTERVIEW_COACH_V1,
        prompt_vars={
            "question": "Tell me about Python",
            "answer": "I used Python",
            "evaluation": "Score: 0.5",
            "language": "en",
        },
        workflow_name="test",
        target_type="interview_answer",
        target_id="test-id",
    )

    assert result["result"]["improved_answer"] == "mock"
    assert result["result"]["explanation"] == "mock"
    assert result["cost"] == 0.0
    assert result["model"] == "test-model"
    assert "usage" in result


@pytest.mark.asyncio
async def test_orchestrator_uses_fallback_on_failure(db_session):
    """Проверяет fallback на резервный клиент при ошибке"""
    orchestrator = AIOrchestrator(
        client=FailingLLMClient(),
        config=AIOrchestratorConfig(
            default_model="test-model",
            max_retries=0,
            enable_tracing=False,
        ),
        fallback_client=MockLLMClient(),
    )

    result = await orchestrator.execute(
        db_session,
        user_id="00000000-0000-0000-0000-000000000001",
        prompt_template=PromptTemplate.INTERVIEW_COACH_V1,
        prompt_vars={
            "question": "Tell me about Python",
            "answer": "I used Python",
            "evaluation": "Score: 0.5",
            "language": "en",
        },
        workflow_name="test",
        target_type="interview_answer",
        target_id="test-id",
    )

    assert result["result"]["improved_answer"] == "mock"
    assert result["result"]["explanation"] == "mock"
    assert result["model"] == "test-model"


@pytest.mark.asyncio
async def test_orchestrator_from_settings_uses_mock_provider(monkeypatch, db_session, test_user):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_DEFAULT_MODEL", "test-model")
    monkeypatch.delenv("AI_FALLBACK_PROVIDER", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        orchestrator = create_ai_orchestrator()
        assert orchestrator.client.provider_name == "mock"

        result = await orchestrator.execute(
            db_session,
            user_id=test_user.id,
            prompt_template=PromptTemplate.INTERVIEW_COACH_V1,
            prompt_vars={
                "question": "Tell me about Python",
                "answer": "I used Python",
                "evaluation": "Score: 0.5",
                "language": "en",
            },
            workflow_name="test",
            target_type="interview_answer",
            target_id="test-id",
        )

        assert result["result"]["improved_answer"] == "mock"
        assert result["model"] == "test-model"
    finally:
        get_settings.cache_clear()
