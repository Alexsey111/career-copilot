from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app

_FERNET_KEY = "2aToT_U2MCPyftyQz2VQ-Nd9uhNlSiz22RLxsJdihPM="


def _has_middleware(app, cls_name: str) -> bool:
    return any(m.cls.__name__ == cls_name for m in app.user_middleware)


def test_trusted_host_middleware_added_when_hosts_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", "example.com,api.example.com")
    get_settings.cache_clear()
    try:
        app = create_app()
        assert _has_middleware(app, "TrustedHostMiddleware")
        assert get_settings().allowed_hosts == ["example.com", "api.example.com"]
    finally:
        get_settings.cache_clear()


def test_trusted_host_middleware_not_added_for_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    get_settings.cache_clear()
    try:
        app = create_app()
        assert not _has_middleware(app, "TrustedHostMiddleware")
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_hsts_header_set_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "safe-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "safe-secret-key")
    monkeypatch.setenv("MINIO_SECURE", "true")
    monkeypatch.setenv("STORAGE_MODE", "s3")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", _FERNET_KEY)
    get_settings.cache_clear()
    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/")
        assert response.status_code == 200
        hsts = response.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_hsts_header_not_set_in_non_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    get_settings.cache_clear()
    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/")
        assert response.status_code == 200
        assert "strict-transport-security" not in response.headers
    finally:
        get_settings.cache_clear()