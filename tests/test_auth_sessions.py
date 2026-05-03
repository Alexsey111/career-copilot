from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.main import app
from app.models import RefreshSession, User

pytestmark = pytest.mark.asyncio

AUTH_PREFIX = "/api/v1/auth"


async def _active_refresh_sessions_count(db_session: AsyncSession) -> int:
    result = await db_session.execute(
        select(RefreshSession).where(RefreshSession.revoked_at.is_(None))
    )
    return len(result.scalars().all())


async def test_refresh_rotates_token_and_revokes_old_session(client, db_session: AsyncSession):
    register_response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "session-rotate@example.com",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 200

    old_refresh = register_response.json()["refresh_token"]
    assert await _active_refresh_sessions_count(db_session) == 1

    refresh_response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refresh_response.status_code == 200

    new_refresh = refresh_response.json()["refresh_token"]
    assert new_refresh != old_refresh
    assert await _active_refresh_sessions_count(db_session) == 1

    old_reuse_response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": old_refresh},
    )
    assert old_reuse_response.status_code == 401

    assert await _active_refresh_sessions_count(db_session) == 0


async def test_logout_revokes_refresh_session(client, db_session: AsyncSession):
    register_response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "session-logout@example.com",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 200

    refresh_token = register_response.json()["refresh_token"]
    assert await _active_refresh_sessions_count(db_session) == 1

    logout_response = await client.post(
        f"{AUTH_PREFIX}/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 200

    assert await _active_refresh_sessions_count(db_session) == 0

    refresh_response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401


async def test_logout_all_revokes_all_user_sessions(client, db_session: AsyncSession):
    first_register = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "session-logout-all@example.com",
            "password": "StrongPass123",
        },
    )
    assert first_register.status_code == 200

    result = await db_session.execute(
        select(User).where(User.email == "session-logout-all@example.com")
    )
    current_user = result.scalars().one()

    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=current_user.id,
        is_active=True,
        is_verified=True,
    )

    login_response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={
            "email": "session-logout-all@example.com",
            "password": "StrongPass123",
        },
    )
    assert login_response.status_code == 200

    assert await _active_refresh_sessions_count(db_session) == 2

    logout_all_response = await client.post(f"{AUTH_PREFIX}/logout-all")
    assert logout_all_response.status_code == 200

    assert await _active_refresh_sessions_count(db_session) == 0
