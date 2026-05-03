from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthEvent, User
from app.security.passwords import hash_password

pytestmark = pytest.mark.asyncio

AUTH_PREFIX = "/api/v1/auth"


async def _event_types(db_session: AsyncSession) -> list[str]:
    result = await db_session.execute(
        select(AuthEvent.event_type).order_by(AuthEvent.created_at.asc())
    )
    return list(result.scalars().all())


async def test_register_writes_auth_event(client, db_session: AsyncSession):
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "audit-register@example.com",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 200
    assert "register" in await _event_types(db_session)


async def test_login_success_writes_auth_event(client, db_session: AsyncSession):
    user = User(
        email="audit-login@example.com",
        password_hash=hash_password("StrongPass123"),
        auth_provider="email",
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={
            "email": "audit-login@example.com",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 200
    assert "login_success" in await _event_types(db_session)


async def test_login_failed_writes_auth_event(client, db_session: AsyncSession):
    response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={
            "email": "missing-user@example.com",
            "password": "WrongPass123",
        },
    )

    assert response.status_code == 401
    assert "login_failed" in await _event_types(db_session)


async def test_login_throttling_after_repeated_failures(
    client,
    db_session: AsyncSession,
):
    for _ in range(5):
        response = await client.post(
            f"{AUTH_PREFIX}/login",
            json={
                "email": "throttle@example.com",
                "password": "WrongPass123",
            },
        )
        assert response.status_code == 401

    throttled_response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={
            "email": "throttle@example.com",
            "password": "WrongPass123",
        },
    )

    assert throttled_response.status_code == 429
    assert "login_throttled" in await _event_types(db_session)


async def test_refresh_success_writes_auth_event(client, db_session: AsyncSession):
    register_response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "audit-refresh@example.com",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 200

    refresh_token = register_response.json()["refresh_token"]

    refresh_response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200
    assert "refresh_success" in await _event_types(db_session)


async def test_refresh_reuse_writes_auth_event(client, db_session: AsyncSession):
    register_response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "audit-refresh-reuse@example.com",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 200

    old_refresh_token = register_response.json()["refresh_token"]

    first_refresh_response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert first_refresh_response.status_code == 200

    reuse_response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert reuse_response.status_code == 401
    assert "refresh_reuse_detected" in await _event_types(db_session)


async def test_logout_all_writes_auth_event(client, db_session: AsyncSession):
    response = await client.post(f"{AUTH_PREFIX}/logout-all")

    assert response.status_code == 200
    assert "logout_all" in await _event_types(db_session)
