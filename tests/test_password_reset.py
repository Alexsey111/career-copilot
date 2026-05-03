from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthEvent, RefreshSession

pytestmark = pytest.mark.asyncio

AUTH_PREFIX = "/api/v1/auth"


async def _event_types(db_session: AsyncSession) -> list[str]:
    result = await db_session.execute(
        select(AuthEvent.event_type).order_by(AuthEvent.created_at.asc())
    )
    return list(result.scalars().all())


async def _active_refresh_sessions_count(db_session: AsyncSession) -> int:
    result = await db_session.execute(
        select(RefreshSession).where(RefreshSession.revoked_at.is_(None))
    )
    return len(result.scalars().all())


async def test_password_reset_end_to_end(client, db_session: AsyncSession):
    email = "password-reset-e2e@example.com"
    old_password = "OldPass123!"
    new_password = "NewStrongPass123"

    register_response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": old_password},
    )
    assert register_response.status_code == 200
    assert await _active_refresh_sessions_count(db_session) == 1

    request_response = await client.post(
        f"{AUTH_PREFIX}/password-reset/request",
        json={"email": email},
    )
    assert request_response.status_code == 200

    reset_token = request_response.json()["reset_token"]
    assert reset_token

    confirm_response = await client.post(
        f"{AUTH_PREFIX}/password-reset/confirm",
        json={
            "reset_token": reset_token,
            "new_password": new_password,
        },
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json() == {"status": "ok"}

    assert await _active_refresh_sessions_count(db_session) == 0

    old_login_response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": old_password},
    )
    assert old_login_response.status_code == 401

    new_login_response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": new_password},
    )
    assert new_login_response.status_code == 200
    assert "access_token" in new_login_response.json()
    assert "refresh_token" in new_login_response.json()

    events = await _event_types(db_session)
    assert "password_reset_requested" in events
    assert "password_reset_completed" in events


async def test_password_reset_token_is_single_use(client):
    email = "password-reset-single-use@example.com"

    register_response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": "OldPass123!"},
    )
    assert register_response.status_code == 200

    request_response = await client.post(
        f"{AUTH_PREFIX}/password-reset/request",
        json={"email": email},
    )
    assert request_response.status_code == 200

    reset_token = request_response.json()["reset_token"]
    assert reset_token

    first_confirm = await client.post(
        f"{AUTH_PREFIX}/password-reset/confirm",
        json={
            "reset_token": reset_token,
            "new_password": "NewStrongPass123",
        },
    )
    assert first_confirm.status_code == 200

    second_confirm = await client.post(
        f"{AUTH_PREFIX}/password-reset/confirm",
        json={
            "reset_token": reset_token,
            "new_password": "AnotherStrongPass123",
        },
    )
    assert second_confirm.status_code == 401


async def test_password_reset_request_does_not_reveal_missing_email(client):
    response = await client.post(
        f"{AUTH_PREFIX}/password-reset/request",
        json={"email": "missing-reset-user@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "reset_token": None,
    }


async def test_password_reset_invalid_token_writes_audit_event(
    client,
    db_session: AsyncSession,
):
    response = await client.post(
        f"{AUTH_PREFIX}/password-reset/confirm",
        json={
            "reset_token": "not-a-real-token",
            "new_password": "NewStrongPass123",
        },
    )

    assert response.status_code == 401
    assert "password_reset_invalid_token" in await _event_types(db_session)