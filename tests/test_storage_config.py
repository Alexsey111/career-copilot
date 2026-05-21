from __future__ import annotations

import pytest

from app.core.config import get_settings


def test_storage_mode_minio_settings_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_MODE", "minio")
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.storage_mode == "minio"
    finally:
        get_settings.cache_clear()


def test_storage_mode_local_is_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "safe-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "safe-secret-key")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:8501")
    monkeypatch.setenv("STORAGE_MODE", "local")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="STORAGE_MODE=local is not allowed in production"):
            get_settings()
    finally:
        get_settings.cache_clear()
