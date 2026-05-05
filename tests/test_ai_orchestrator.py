from __future__ import annotations

import pytest

from app.ai.orchestrator import AIOrchestrator
from app.ai.config import AIOrchestratorConfig
from app.ai.registry.prompts import PromptTemplate


@pytest.mark.asyncio
async def test_orchestrator_stub_returns_empty_result(db_session):
    """Проверяет, что заглушка возвращает корректную структуру"""
    orchestrator = AIOrchestrator(
        config=AIOrchestratorConfig(default_model="test-model"),
    )
    
    result = await orchestrator.execute(
        db_session,
        user_id="test-user-id",
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={"vacancy_title": "Test", "company": "TestCo"},
        workflow_name="test",
        target_type="vacancy",
        target_id="test-id",
    )
    
    assert result["result"] == ""
    assert result["cost"] == 0.0
    assert result["model"] == "test-model"
    assert "usage" in result


@pytest.mark.asyncio
async def test_orchestrator_stub_uses_default_config(db_session):
    """Проверяет конфигурацию по умолчанию"""
    orchestrator = AIOrchestrator()

    result = await orchestrator.execute(
        db_session,
        user_id="test-user-id",
        prompt_template=PromptTemplate.COVER_LETTER_V1,
        prompt_vars={},
        workflow_name="test",
        target_type="vacancy",
        target_id="test-id",
    )
    
    assert result["model"] == "gigachat-pro"
    assert result["cost"] == 0.0