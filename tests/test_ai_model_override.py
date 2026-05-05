# tests/test_ai_model_override.py

import pytest
from uuid import uuid4

from app.api.ai.orchestrator import AIOrchestrator
from app.api.ai.clients.base import BaseLLMClient


from app.api.ai.registry.prompts import PromptTemplate


class MockClient(BaseLLMClient):
    async def generate(self, prompt: str, **kwargs):
        return {
            "content": "ok",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": kwargs.get("model"),
        }

    async def generate_structured(self, prompt: str, output_schema: dict, **kwargs):
        return {
            "content": {"ok": True},
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": kwargs.get("model"),
        }

    @property
    def provider_name(self):
        return "mock"


@pytest.mark.asyncio
async def test_model_override(db_session, test_user):
    client = MockClient()
    orchestrator = AIOrchestrator(client=client)

    result = await orchestrator.execute(
        session=db_session,
        user_id=test_user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={
            "vacancy_title": "Test",
            "company": "TestCo",
            "must_have": ["Python"],
            "profile_summary": "Developer",
            "confirmed_achievements": [],
        },
        workflow_name="test",
        target_type="test",
        model_override="gigachat-lite",
    )

    assert result["model"] == "gigachat-lite"