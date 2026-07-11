# tests/test_cost_accounting.py

"""Этап 2.2 — учёт стоимости AI-запросов (ТЗ §3.4 cost accounting)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.clients.gigachat import GigaChatClient
from app.ai.config import AIOrchestratorConfig
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate
from app.models import AIRun


def _gigachat_mock_client():
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
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        "model": "gigachat-pro",
    }
    mock_http_client.post = AsyncMock(return_value=mock_response)

    mock_settings = Mock()
    mock_settings.gigachat_api_key = "k"
    mock_settings.gigachat_base_url = "https://test.api"
    mock_settings.ai_request_timeout = 30.0

    with patch("app.ai.clients.gigachat.get_settings", return_value=mock_settings):
        with patch(
            "app.ai.clients.gigachat.httpx.AsyncClient", return_value=mock_http_client
        ):
            return GigaChatClient()


@pytest.mark.asyncio
async def test_cost_computed_and_stored_on_ai_run(db_session, test_user):
    client = _gigachat_mock_client()
    config = AIOrchestratorConfig(
        default_model="gigachat-pro",
        cost_per_1k_tokens_input=0.01,
        cost_per_1k_tokens_output=0.03,
        enable_tracing=True,
    )
    orchestrator = AIOrchestrator(client=client, config=config)

    result = await orchestrator.execute(
        db_session,
        user_id=test_user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={
            "vacancy_title": "T",
            "company": "C",
            "must_have": ["Python"],
            "profile_summary": "Dev",
            "confirmed_achievements": [],
        },
        workflow_name="cost_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )

    # 1000 input * 0.01/1k + 500 output * 0.03/1k = 0.01 + 0.015 = 0.025
    assert result["cost"] == pytest.approx(0.025, rel=1e-6)

    ai_run = (
        await db_session.execute(
            select(AIRun).where(AIRun.workflow_name == "cost_test")
        )
    ).scalar_one()
    assert float(ai_run.cost) == pytest.approx(0.025, rel=1e-6)


@pytest.mark.asyncio
async def test_cost_zero_when_rates_unset(db_session, test_user):
    client = _gigachat_mock_client()
    config = AIOrchestratorConfig(default_model="gigachat-pro")  # rates = 0
    orchestrator = AIOrchestrator(client=client, config=config)

    result = await orchestrator.execute(
        db_session,
        user_id=test_user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={
            "vacancy_title": "T",
            "company": "C",
            "must_have": ["Python"],
            "profile_summary": "Dev",
            "confirmed_achievements": [],
        },
        workflow_name="cost_zero_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )
    assert result["cost"] == 0.0


@pytest.mark.asyncio
async def test_ai_usage_endpoint_aggregates(client, db_session, test_user):
    db_session.add(
        AIRun(
            user_id=test_user.id,
            workflow_name="resume_tailoring",
            target_type="vacancy",
            status="completed",
            provider_name="gigachat",
            model_name="gigachat-pro",
            tokens_used_json={"prompt_tokens": 100, "completion_tokens": 50},
            cost=0.5,
            input_snapshot_json={},
            output_snapshot_json={},
        )
    )
    db_session.add(
        AIRun(
            user_id=test_user.id,
            workflow_name="resume_tailoring",
            target_type="vacancy",
            status="completed",
            provider_name="gigachat",
            model_name="gigachat-pro",
            tokens_used_json={"prompt_tokens": 200, "completion_tokens": 100},
            cost=1.5,
            input_snapshot_json={},
            output_snapshot_json={},
        )
    )
    db_session.add(
        AIRun(
            user_id=test_user.id,
            workflow_name="interview_coach",
            target_type="vacancy",
            status="failed",
            provider_name="gigachat",
            model_name="gigachat-pro",
            tokens_used_json={"prompt_tokens": 10, "completion_tokens": 0},
            cost=None,
            input_snapshot_json={},
            output_snapshot_json={},
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/me/ai-usage")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_runs"] == 3
    assert body["total_tokens"] == 460
    assert float(body["total_cost"]) == pytest.approx(2.0, rel=1e-6)

    by_wf = {b["workflow"]: b for b in body["by_workflow"]}
    assert by_wf["resume_tailoring"]["runs"] == 2
    assert by_wf["resume_tailoring"]["total_tokens"] == 450
    assert float(by_wf["resume_tailoring"]["total_cost"]) == pytest.approx(2.0, rel=1e-6)
    assert by_wf["interview_coach"]["runs"] == 1
    assert float(by_wf["interview_coach"]["total_cost"]) == 0.0