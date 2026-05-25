from __future__ import annotations

import pytest

from app.ai.clients.mock import MockLLMClient
from app.ai.factory import create_ai_orchestrator
from app.core.config import get_settings


def _set_minimum_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://career_user:career_pass@localhost:5432/career_copilot",
    )
    monkeypatch.setenv(
        "SYNC_DATABASE_URL",
        "postgresql+psycopg://career_user:career_pass@localhost:5432/career_copilot",
    )
    monkeypatch.setenv("MINIO_ACCESS_KEY", "safe-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "safe-secret-key")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:8501")


def test_ai_provider_mock_is_supported_in_test_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_FALLBACK_PROVIDER", "mock")
    monkeypatch.setenv("AI_FALLBACK_MODEL", "mock-fallback-model")
    get_settings.cache_clear()

    try:
        orchestrator = create_ai_orchestrator()

        assert isinstance(orchestrator.client, MockLLMClient)
        assert orchestrator.client.provider_name == "mock"
        assert isinstance(orchestrator.fallback_client, MockLLMClient)
        assert orchestrator.fallback_client.provider_name == "mock"
        assert orchestrator.config.fallback_model == "mock-fallback-model"
    finally:
        get_settings.cache_clear()


def test_ai_provider_mock_is_rejected_in_production(monkeypatch):
    _set_minimum_production_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="AI_PROVIDER=mock is not allowed in production"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_ai_fallback_provider_mock_is_rejected_in_production(monkeypatch):
    _set_minimum_production_env(monkeypatch)
    monkeypatch.setenv("AI_FALLBACK_PROVIDER", "mock")
    get_settings.cache_clear()

    try:
        with pytest.raises(
            ValueError,
            match="AI_FALLBACK_PROVIDER=mock is not allowed in production",
        ):
            get_settings()
    finally:
        get_settings.cache_clear()
