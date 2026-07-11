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
    monkeypatch.setenv("MINIO_SECURE", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:8501")
    monkeypatch.setenv("STORAGE_MODE", "local")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="STORAGE_MODE=local is not allowed in production"):
            get_settings()
    finally:
        get_settings.cache_clear()


def _prod_safe_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "safe-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "safe-secret-key")
    monkeypatch.setenv("MINIO_SECURE", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("STORAGE_MODE", "s3")


def test_field_encryption_keys_missing_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_safe_env(monkeypatch)
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEYS is missing in production"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_field_encryption_keys_invalid_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_safe_env(monkeypatch)
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", "not-a-valid-fernet-key")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEYS contains an invalid Fernet key"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_field_encryption_keys_valid_accepted_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_safe_env(monkeypatch)
    monkeypatch.setenv(
        "FIELD_ENCRYPTION_KEYS",
        "2aToT_U2MCPyftyQz2VQ-Nd9uhNlSiz22RLxsJdihPM=",
    )
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.field_encryption_keys == ["2aToT_U2MCPyftyQz2VQ-Nd9uhNlSiz22RLxsJdihPM="]
    finally:
        get_settings.cache_clear()


def test_minio_secure_false_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_safe_env(monkeypatch)
    monkeypatch.setenv("MINIO_SECURE", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="MINIO_SECURE must be true in production"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_cors_http_non_localhost_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_safe_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://example.com")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS must use HTTPS in production"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_cors_http_localhost_allowed_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_safe_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:8501")
    monkeypatch.setenv(
        "FIELD_ENCRYPTION_KEYS",
        "2aToT_U2MCPyftyQz2VQ-Nd9uhNlSiz22RLxsJdihPM=",
    )
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.cors_allowed_origins == ["http://localhost:8501"]
    finally:
        get_settings.cache_clear()
