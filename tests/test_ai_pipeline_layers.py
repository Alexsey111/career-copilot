# tests/test_ai_pipeline_layers.py

"""Этап 2.4 — pipeline-слои ContextBuilder и ModelRouter (ТЗ §3.4)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.config import AIOrchestratorConfig
from app.ai.context_builder import ContextBuilder
from app.ai.model_router import ModelRouter
from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


def test_model_router_override_wins_over_hint_and_default():
    router = ModelRouter(overrides={"resume_tailoring": "gigachat-lite"})
    assert (
        router.select_model(
            workflow_name="resume_tailoring",
            model_hint="gigachat-pro",
            default_model="gigachat-pro",
        )
        == "gigachat-lite"
    )


def test_model_router_explicit_override_wins_over_map():
    router = ModelRouter(overrides={"resume_tailoring": "gigachat-lite"})
    assert (
        router.select_model(
            workflow_name="resume_tailoring",
            model_override="custom-model",
            model_hint="gigachat-pro",
            default_model="gigachat-pro",
        )
        == "custom-model"
    )


def test_model_router_hint_wins_over_default():
    router = ModelRouter()
    assert (
        router.select_model(
            workflow_name="resume_tailoring",
            model_hint="hinted-model",
            default_model="default-model",
        )
        == "hinted-model"
    )


def test_model_router_default_fallback():
    router = ModelRouter()
    assert (
        router.select_model(workflow_name="resume_tailoring", default_model="d")
        == "d"
    )


def test_context_builder_truncates_long_strings():
    builder = ContextBuilder(max_field_length=10)
    out = builder.normalize({"summary": "x" * 100, "skills": ["a", "b"]})
    assert len(out["summary"]) == 10
    assert out["skills"] == ["a", "b"]


def test_context_builder_leaves_short_strings():
    builder = ContextBuilder(max_field_length=100)
    out = builder.normalize({"summary": "short"})
    assert out["summary"] == "short"


def test_context_builder_adds_language_only_when_spec_expects_it():
    builder = ContextBuilder()
    with_lang = builder.normalize(
        {"x": "y"}, spec_input_keys=["x", "language"], language="ru"
    )
    assert with_lang["language"] == "ru"

    without_lang = builder.normalize(
        {"x": "y"}, spec_input_keys=["x"], language="ru"
    )
    assert "language" not in without_lang


def test_context_builder_does_not_overwrite_explicit_language():
    builder = ContextBuilder()
    out = builder.normalize(
        {"language": "en"}, spec_input_keys=["language"], language="ru"
    )
    assert out["language"] == "en"


@pytest.mark.asyncio
async def test_orchestrator_uses_model_router_override(db_session, test_user):
    """Per-workflow карта маршрутизации пробрасывается в выбор модели."""
    client = AsyncMock()
    client.provider_name = "fake"
    client.generate_structured = AsyncMock(
        return_value={
            "content": {"summary": "s", "skills": [], "experience_highlights": []},
            "usage": {},
            "model": "captured",
        }
    )
    client.aclose = AsyncMock()

    config = AIOrchestratorConfig(default_model="default-model", enable_tracing=False)
    orchestrator = AIOrchestrator(client=client, config=config)

    # Патчим карту маршрутизации: workflow router_test → routed-model.
    import app.ai.model_router as mr_module

    original = mr_module._WORKFLOW_MODEL_OVERRIDES.copy()
    mr_module._WORKFLOW_MODEL_OVERRIDES["router_test"] = "routed-model"
    try:
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
            workflow_name="router_test",
            target_type="vacancy",
            target_id=str(uuid4()),
        )
    finally:
        mr_module._WORKFLOW_MODEL_OVERRIDES.clear()
        mr_module._WORKFLOW_MODEL_OVERRIDES.update(original)

    # Модель, переданная в клиент, должна быть из карты маршрутизации.
    call_kwargs = client.generate_structured.call_args.kwargs
    assert call_kwargs["model"] == "routed-model"
    assert result["model"] == "routed-model"