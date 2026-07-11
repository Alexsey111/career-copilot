# tests/test_ai_caching.py

"""Этап 2.3 — кэширование ответов AI (ТЗ §3.4 «caching»)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.cache import make_cache_key, reset_cache_for_tests
from app.ai.config import AIOrchestratorConfig
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


class CountingFakeClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.structured_calls = 0

    async def generate_structured(self, **kwargs):
        self.structured_calls += 1
        return {
            "content": {"summary": "x", "skills": ["Python"], "experience_highlights": []},
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "fake-model",
        }

    async def generate(self, **kwargs):
        return {"content": "ok", "usage": {}, "model": "fake-model"}

    async def aclose(self):
        pass


_PROMPT_VARS = {
    "vacancy_title": "T",
    "company": "C",
    "must_have": ["Python"],
    "profile_summary": "Dev",
    "confirmed_achievements": [],
}


@pytest.fixture(autouse=True)
def _reset_ai_cache():
    reset_cache_for_tests()
    yield
    reset_cache_for_tests()


def test_cache_key_is_deterministic():
    k1 = make_cache_key(prompt_version="v1", model="m", temperature=0.1, prompt="p")
    k2 = make_cache_key(prompt_version="v1", model="m", temperature=0.1, prompt="p")
    k3 = make_cache_key(prompt_version="v1", model="m", temperature=0.1, prompt="p2")
    assert k1 == k2
    assert k1 != k3


@pytest.mark.asyncio
async def test_cache_hit_skips_llm_call(db_session, test_user):
    client = CountingFakeClient()
    config = AIOrchestratorConfig(
        default_model="fake-model",
        enable_cache=True,
        enable_tracing=False,
    )
    orchestrator = AIOrchestrator(client=client, config=config)

    common = dict(
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars=_PROMPT_VARS,
        workflow_name="cache_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )

    first = await orchestrator.execute(db_session, user_id=test_user.id, **common)
    second = await orchestrator.execute(db_session, user_id=test_user.id, **common)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    # LLM вызван ровно один раз — второй запрос ушёл в кэш.
    assert client.structured_calls == 1
    assert second["result"] == first["result"]


@pytest.mark.asyncio
async def test_cache_disabled_calls_llm_each_time(db_session, test_user):
    client = CountingFakeClient()
    config = AIOrchestratorConfig(
        default_model="fake-model",
        enable_cache=False,
        enable_tracing=False,
    )
    orchestrator = AIOrchestrator(client=client, config=config)

    common = dict(
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars=_PROMPT_VARS,
        workflow_name="no_cache_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )

    first = await orchestrator.execute(db_session, user_id=test_user.id, **common)
    second = await orchestrator.execute(db_session, user_id=test_user.id, **common)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is False
    assert client.structured_calls == 2


@pytest.mark.asyncio
async def test_different_prompt_vars_miss_cache(db_session, test_user):
    client = CountingFakeClient()
    config = AIOrchestratorConfig(
        default_model="fake-model",
        enable_cache=True,
        enable_tracing=False,
    )
    orchestrator = AIOrchestrator(client=client, config=config)

    await orchestrator.execute(
        db_session,
        user_id=test_user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={**_PROMPT_VARS, "vacancy_title": "A"},
        workflow_name="miss_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )
    await orchestrator.execute(
        db_session,
        user_id=test_user.id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={**_PROMPT_VARS, "vacancy_title": "B"},
        workflow_name="miss_test",
        target_type="vacancy",
        target_id=str(uuid4()),
    )

    assert client.structured_calls == 2