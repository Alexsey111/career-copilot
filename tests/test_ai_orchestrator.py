from __future__ import annotations

import pytest

from app.ai.orchestrator import AIOrchestrator
from app.ai.config import AIOrchestratorConfig
from app.ai.clients.base import BaseLLMClient, LLMClientError
from app.ai.registry.prompts import PromptTemplate


class MockLLMClient(BaseLLMClient):
    """Мок-клиент для тестов orchestrator"""

    @property
    def provider_name(self):
        return "mock"

    async def generate(self, *args, **kwargs):
        return {
            "content": "test response",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "mock-model",
        }

    async def generate_structured(self, prompt, output_schema, **kwargs):
        return {
            "content": {"improved_answer": "test"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "mock-model",
        }


class FailingLLMClient(BaseLLMClient):
    """Клиент, который всегда падает"""

    @property
    def provider_name(self):
        return "failing-mock"

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
        user_id="test-user-id",
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

    assert result["result"] == {"improved_answer": "test"}
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
        user_id="test-user-id",
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

    assert result["result"] == {"improved_answer": "test"}
    assert result["model"] == "test-model"
