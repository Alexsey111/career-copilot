# tests/test_data_transfer_audit.py

"""Аудит передачи ПДн AI-провайдеру (ФЗ-152 ст.18/19)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.clients.gigachat import GigaChatClient
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate
from app.models import DataTransferEvent


@pytest.mark.asyncio
async def test_orchestrator_execute_logs_data_transfer_event(db_session, test_user):
    mock_settings = Mock()
    mock_settings.gigachat_api_key = "test-key"
    mock_settings.gigachat_base_url = "https://test.api"
    mock_settings.ai_request_timeout = 30.0
    mock_settings.ai_default_model = "gigachat-pro"
    mock_settings.ai_max_retries = 3
    mock_settings.ai_temperature = 0.1

    mock_http_client = AsyncMock()
    mock_http_client.close = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"summary": "test", "skills": ["Python"], "experience_highlights": []}'
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": "gigachat-pro",
    }
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch("app.ai.clients.gigachat.get_settings", return_value=mock_settings):
        with patch(
            "app.ai.clients.gigachat.httpx.AsyncClient", return_value=mock_http_client
        ):
            client = GigaChatClient()

    orchestrator = AIOrchestrator(client=client)

    await orchestrator.execute(
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
        workflow_name="transfer_audit_test",
        target_type="vacancy",
        target_id=str(uuid4()),
        data_categories=["profile", "resume_text"],
    )

    stmt = select(DataTransferEvent).where(
        DataTransferEvent.user_id == test_user.id
    )
    event = (await db_session.execute(stmt)).scalar_one()

    assert event.recipient == "gigachat"
    assert event.purpose == "transfer_audit_test"
    assert event.legal_basis == "consent"
    assert event.consent_type == "ai_generation"
    assert event.model_name == "gigachat-pro"
    assert event.data_categories == ["profile", "resume_text"]


@pytest.mark.asyncio
async def test_data_transfer_event_default_categories(db_session, test_user):
    mock_settings = Mock()
    mock_settings.gigachat_api_key = "test-key"
    mock_settings.gigachat_base_url = "https://test.api"
    mock_settings.ai_request_timeout = 30.0
    mock_settings.ai_default_model = "gigachat-pro"
    mock_settings.ai_max_retries = 3
    mock_settings.ai_temperature = 0.1

    mock_http_client = AsyncMock()
    mock_http_client.close = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"summary": "test", "skills": ["Python"], "experience_highlights": []}'
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": "gigachat-pro",
    }
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch("app.ai.clients.gigachat.get_settings", return_value=mock_settings):
        with patch(
            "app.ai.clients.gigachat.httpx.AsyncClient", return_value=mock_http_client
        ):
            client = GigaChatClient()

    orchestrator = AIOrchestrator(client=client)

    # data_categories не передаётся → должен быть дефолт ["personal_data"].
    await orchestrator.execute(
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
        workflow_name="default_cat_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )

    event = (
        await db_session.execute(
            select(DataTransferEvent).where(
                DataTransferEvent.purpose == "default_cat_test"
            )
        )
    ).scalar_one()
    assert event.data_categories == ["personal_data"]