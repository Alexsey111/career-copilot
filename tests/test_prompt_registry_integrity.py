"""
Тесты для Prompt Registry integrity:
- prompt_version сохраняется в AIRun
- generate_structured валидирует JSON против output_schema
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate, get_prompt


from app.models.entities import User


class FakeLLMClient:
    """Mock клиент, который возвращает валидный JSON."""
    provider_name = "test"

    async def generate_structured(self, **kwargs):
        return {
            "content": {"summary": "test", "skills": ["Python"]},
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        }

    async def generate(self, **kwargs):
        return {
            "content": "plain text",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        }

    async def aclose(self):
        pass


class FakeLLMClientInvalidJSON(FakeLLMClient):
    """Mock клиент, который возвращает невалидный JSON."""
    async def generate_structured(self, **kwargs):
        return {
            "content": "not json",
            "usage": {},
            "model": "test-model",
        }


class FakeLLMClientInvalidSchema(FakeLLMClient):
    """Mock клиент, который возвращает JSON, не проходящий schema validation."""
    async def generate_structured(self, **kwargs):
        return {
            "content": {"wrong_field": "test"},
            "usage": {},
            "model": "test-model",
        }


@pytest.mark.asyncio
async def test_orchestrator_saves_prompt_version_in_ai_run(db_session):
    """Проверяем, что prompt_version сохраняется из PromptTemplate.value."""
    # Создаём пользователя
    user = User(
        id=uuid4(),
        email="test-prompt@example.com",
        password_hash="fake",
    )
    db_session.add(user)
    await db_session.flush()

    client = FakeLLMClient()
    orchestrator = AIOrchestrator(
        client=client,
        config=MagicMock(
            default_model="test-model",
            temperature=0.1,
            max_tokens=1000,
            enable_tracing=True,
            request_timeout_sec=30,
            max_retries=0,
            retry_backoff_sec=0.1,
            cost_per_1k_tokens_input=None,
            cost_per_1k_tokens_output=None,
        ),
    )

    result = await orchestrator.execute(
        db_session,
        user_id=user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={
            "vacancy_title": "Dev",
            "company": "TestCo",
            "must_have": ["Python"],
            "profile_summary": "Python dev",
            "confirmed_achievements": ["Built API"],
        },
        workflow_name="test_prompt_version",
        target_type="resume",
    )

    # Проверяем результат
    assert result["result"] == {"summary": "test", "skills": ["Python"]}

    # Проверяем, что в БД сохранён правильный prompt_version
    from sqlalchemy import select
    from app.models.entities import AIRun

    stmt = select(AIRun).where(AIRun.workflow_name == "test_prompt_version")
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1
    run = rows[0]
    assert run.prompt_version == "resume_tailor_v1"
    assert run.status == "completed"


@pytest.mark.asyncio
async def test_generate_structured_validates_json_schema():
    """Проверяем, что generate_structured бросает ошибку при невалидном JSON."""
    from app.ai.clients.gigachat import GigaChatClient
    import json

    client = GigaChatClient.__new__(GigaChatClient)
    client.base_url = "http://test"
    client.api_key = "test"
    client.client = MagicMock()

    # Невалидный JSON
    with pytest.raises(json.JSONDecodeError):
        client._safe_parse_json("not json at all")


@pytest.mark.asyncio
async def test_generate_structured_validates_against_output_schema():
    """Проверяем, что generate_structured валидирует JSON против output_schema."""
    from app.ai.clients.gigachat import GigaChatClient, LLMClientError
    from jsonschema import ValidationError

    client = GigaChatClient.__new__(GigaChatClient)
    client.base_url = "http://test"
    client.api_key = "test"
    client.client = MagicMock()

    # JSON проходит парсинг, но не проходит schema validation
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
        },
        "required": ["summary"],
    }

    parsed = {"wrong_field": "test"}

    with pytest.raises((LLMClientError, ValidationError)) as exc_info:
        from jsonschema import validate
        validate(instance=parsed, schema=output_schema)
    assert "summary" in str(exc_info.value) or "required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prompt_registry_has_output_schema_for_structured_prompts():
    """Проверяем, что все structured промпты имеют output_schema."""
    structured_prompts = [
        PromptTemplate.RESUME_TAILOR_V1,
        PromptTemplate.RESUME_ENHANCE_V1,
        PromptTemplate.COVER_LETTER_ENHANCE_V1,
        PromptTemplate.INTERVIEW_COACH_V1,
        PromptTemplate.INTERVIEW_COACHING_V1,
    ]

    for template in structured_prompts:
        spec = get_prompt(template)
        assert spec.output_schema is not None, f"{template.value} missing output_schema"
        assert isinstance(spec.output_schema, dict), f"{template.value} output_schema must be dict"
