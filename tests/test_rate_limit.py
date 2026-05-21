from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import clear_rate_limits_for_tests
from app.main import app


def test_login_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_rate_limits_for_tests()

    client = TestClient(app)

    payload = {"email": "missing@example.com", "password": "wrong-password"}

    first = client.post("/api/v1/auth/login", json=payload)
    second = client.post("/api/v1/auth/login", json=payload)

    assert first.status_code in {401, 422}
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limit_exceeded"

    get_settings.cache_clear()
    clear_rate_limits_for_tests()


def test_rate_limit_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_rate_limits_for_tests()

    client = TestClient(app)

    payload = {"email": "missing2@example.com", "password": "wrong-password"}

    first = client.post("/api/v1/auth/login", json=payload)
    second = client.post("/api/v1/auth/login", json=payload)

    assert first.status_code in {401, 422}
    assert second.status_code in {401, 422}

    get_settings.cache_clear()
    clear_rate_limits_for_tests()
