# tests/test_ai_smoke.py
"""Smoke tests для AI клиента и оркестратора."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.api.ai.clients.gigachat import GigaChatClient
from app.api.ai.orchestrator import AIOrchestrator
from app.api.ai.registry.prompts import PromptTemplate
from app.models.entities import AIRun


@pytest.mark.asyncio
async def test_gigachat_client_generate_smoke():
    """Smoke test: мокнутый HTTP → клиент возвращает OK."""
    from unittest.mock import PropertyMock

    # Мокаем get_settings до создания клиента
    mock_settings = Mock()
    mock_settings.gigachat_api_key = "test-key"
    mock_settings.gigachat_base_url = "https://test.api"
    mock_settings.ai_request_timeout = 30.0

    # Мокаем httpx.AsyncClient целиком
    mock_http_client = AsyncMock()
    mock_http_client.close = AsyncMock()

    # Мокаем HTTP-ответ
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "OK"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        "model": "gigachat-pro",
    }
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch("app.api.ai.clients.gigachat.get_settings", return_value=mock_settings):
        with patch("app.api.ai.clients.gigachat.httpx.AsyncClient", return_value=mock_http_client):
            client = GigaChatClient()

    result = await client.generate("Say OK")

    assert result["content"] == "OK"
    assert result["usage"]["prompt_tokens"] == 5


@pytest.mark.asyncio
async def test_orchestrator_execute_creates_ai_run(db_session, test_user):
    """Через orchestrator.execute → появляется запись в ai_runs."""
    from unittest.mock import PropertyMock

    # Мокаем get_settings до создания клиента
    mock_settings = Mock()
    mock_settings.gigachat_api_key = "test-key"
    mock_settings.gigachat_base_url = "https://test.api"
    mock_settings.ai_request_timeout = 30.0
    mock_settings.ai_default_model = "gigachat-pro"
    mock_settings.ai_max_retries = 3
    mock_settings.ai_temperature = 0.1

    # Мокаем httpx.AsyncClient целиком
    mock_http_client = AsyncMock()
    mock_http_client.close = AsyncMock()

    # Мокаем HTTP-ответ (structured JSON)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": '{"summary": "test"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": "gigachat-pro",
    }
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch("app.api.ai.clients.gigachat.get_settings", return_value=mock_settings):
        with patch("app.api.ai.clients.gigachat.httpx.AsyncClient", return_value=mock_http_client):
            client = GigaChatClient()

    orchestrator = AIOrchestrator(client=client)

    result = await orchestrator.execute(
        db_session,
        user_id=test_user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={
            "vacancy_title": "Test",
            "company": "TestCo",
            "must_have": ["Python"],
            "profile_summary": "Dev",
            "confirmed_achievements": [],
        },
        workflow_name="smoke_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )

    # Проверяем результат
    assert result["model"] == "gigachat-pro"
    assert "result" in result

    # Проверяем БД
    stmt = select(AIRun).where(AIRun.workflow_name == "smoke_test")
    ai_run = (await db_session.execute(stmt)).scalar_one_or_none()

    assert ai_run is not None
    assert ai_run.provider_name == "gigachat"
    assert ai_run.status == "completed"
    assert ai_run.model_name == "gigachat-pro"
