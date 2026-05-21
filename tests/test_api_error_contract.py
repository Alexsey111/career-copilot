from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_http_exception_uses_error_envelope(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    get_settings.cache_clear()
    client = TestClient(app)

    try:
        response = client.get("/health/db-info")

        assert response.status_code == 404
        body = response.json()

        assert "error" in body
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"] == "Not found"
        assert "correlation_id" in body["error"]
        assert "details" in body["error"]
    finally:
        get_settings.cache_clear()


def test_validation_error_uses_error_envelope() -> None:
    client = TestClient(app)

    response = client.post("/api/v1/auth/login", json={})

    assert response.status_code == 422
    body = response.json()

    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert "errors" in body["error"]["details"]


def test_auth_error_preserves_www_authenticate_header() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    body = response.json()
    assert body["error"]["code"] == "unauthorized"
