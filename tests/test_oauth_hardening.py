from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select, text

from app.core.config import get_settings
from app.models import AuthEvent, User
from app.services.oauth_service import (
    OAuthService,
    OAuthUserInfo,
    _state_key,
    generate_oauth_state,
    verify_oauth_state,
)

_VALID_STATE_KEY = "0123456789abcdef0123456789abcdef"
_OAUTH_SUCCESS_EMAIL = "oauth-success@example.com"


def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", _VALID_STATE_KEY)
    get_settings.cache_clear()


# --- signed state ----------------------------------------------------------


def test_state_round_trip_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_secret(monkeypatch)
    state = generate_oauth_state("google")
    assert verify_oauth_state(state, "google") is True


def test_state_missing_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_secret(monkeypatch)
    assert verify_oauth_state("", "google") is False
    assert verify_oauth_state(None, "google") is False  # type: ignore[arg-type]


def test_state_tampered_signature_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_secret(monkeypatch)
    state = generate_oauth_state("google")
    payload, _sig = state.rsplit(".", 1)
    tampered = f"{payload}.{'0' * 64}"
    assert verify_oauth_state(tampered, "google") is False


def test_state_cross_provider_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_secret(monkeypatch)
    state = generate_oauth_state("google")
    assert verify_oauth_state(state, "github") is False


def test_state_expired_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_jwt_secret(monkeypatch)
    state = generate_oauth_state("google")
    payload, _sig = state.rsplit(".", 1)
    _provider, _ts, nonce = payload.split(":")
    old_ts = str(int(time.time()) - 3600)
    old_payload = f"google:{old_ts}:{nonce}"
    sig = hmac.new(_state_key(), old_payload.encode(), hashlib.sha256).hexdigest()
    old_state = f"{old_payload}.{sig}"
    assert verify_oauth_state(old_state, "google", max_age_seconds=600) is False


# --- endpoint rejects invalid state (CSRF guard) ---------------------------


@pytest.mark.asyncio
async def test_callback_rejects_missing_state(client) -> None:
    response = await client.post("/api/v1/auth/oauth/google/callback?code=fake")
    assert response.status_code == 400
    assert "Invalid or expired OAuth state" in response.json()["detail"]


@pytest.mark.asyncio
async def test_callback_rejects_invalid_state(client) -> None:
    response = await client.post(
        "/api/v1/auth/oauth/google/callback?code=fake&state=bogus.state"
    )
    assert response.status_code == 400
    assert "Invalid or expired OAuth state" in response.json()["detail"]


# --- service-level: verified email + audit IP/UA ---------------------------


def _fake_request(ip: str = "203.0.113.5", user_agent: str = "oauth-test-ua/1.0") -> Request:
    return Request(
        scope={
            "type": "http",
            "client": (ip, 12345),
            "headers": [(b"user-agent", user_agent.encode())],
        }
    )


async def _fake_google_exchange(self: OAuthService, code: str) -> dict:
    return {"access_token": "fake-google-access-token"}


async def _fake_google_userinfo_verified(self: OAuthService, access_token: str) -> OAuthUserInfo:
    return OAuthUserInfo(
        provider="google",
        provider_id="g-123",
        email=_OAUTH_SUCCESS_EMAIL,
        email_verified=True,
        name="OAuth User",
    )


async def _fake_google_userinfo_unverified(self: OAuthService, access_token: str) -> OAuthUserInfo:
    return OAuthUserInfo(
        provider="google",
        provider_id="g-456",
        email="unverified@example.com",
        email_verified=False,
        name="OAuth User",
    )


class _SessionCtx:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc) -> bool:
        return False


def _patch_sessionmaker(monkeypatch: pytest.MonkeyPatch, session) -> None:
    import app.services.oauth_service as oauth_service

    monkeypatch.setattr(oauth_service, "AsyncSessionLocal", lambda: _SessionCtx(session))


@pytest.mark.asyncio
async def test_oauth_login_rejects_unverified_email(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_jwt_secret(monkeypatch)
    monkeypatch.setattr(OAuthService, "_exchange_google_code", _fake_google_exchange)
    monkeypatch.setattr(OAuthService, "_get_google_userinfo", _fake_google_userinfo_unverified)

    service = OAuthService()
    with pytest.raises(HTTPException) as exc:
        await service.handle_google_callback("fake-code", _fake_request())
    assert exc.value.status_code == 400
    assert "verified email" in exc.value.detail


@pytest.mark.asyncio
async def test_oauth_login_success_records_audit_with_real_request(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_jwt_secret(monkeypatch)
    monkeypatch.setattr(OAuthService, "_exchange_google_code", _fake_google_exchange)
    monkeypatch.setattr(OAuthService, "_get_google_userinfo", _fake_google_userinfo_verified)
    _patch_sessionmaker(monkeypatch, db_session)

    service = OAuthService()
    tokens = await service.handle_google_callback("fake-code", _fake_request())

    assert tokens.access_token
    assert tokens.refresh_token

    user = (
        await db_session.execute(select(User).where(User.email == _OAUTH_SUCCESS_EMAIL))
    ).scalar_one()
    assert user.is_verified is True
    assert user.auth_provider == "google"

    # OAuth access token is stored encrypted at rest (Этап 1.1).
    raw_token = await db_session.scalar(
        text("SELECT oauth_access_token FROM users WHERE id = :id"),
        {"id": user.id},
    )
    assert raw_token != "fake-google-access-token"
    assert "fake-google-access-token" not in raw_token

    # Audit event carries the real request IP/UA (not a fake/empty Request).
    audit = (
        await db_session.execute(
            select(AuthEvent).where(
                AuthEvent.user_id == user.id,
                AuthEvent.event_type == "oauth_register",
            )
        )
    ).scalar_one()
    assert audit.ip_address == "203.0.113.5"
    assert audit.user_agent == "oauth-test-ua/1.0"