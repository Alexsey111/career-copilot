from __future__ import annotations

import bcrypt
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthEvent, User
from app.security.passwords import is_argon2_hash

pytestmark = pytest.mark.asyncio

AUTH_PREFIX = "/api/v1/auth"
CONSENT_PREFIX = "/api/v1/consent"


def _bcrypt_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def _event_types(db_session: AsyncSession) -> list[str]:
    result = await db_session.execute(
        select(AuthEvent.event_type).order_by(AuthEvent.created_at.asc())
    )
    return list(result.scalars().all())


async def test_login_migrates_bcrypt_hash_to_argon2(client, db_session: AsyncSession):
    email = "bcrypt-migration@example.com"
    password = "Migrate-Me-123!"

    register = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": password},
    )
    assert register.status_code == 200

    # Подменяем argon2-хэш на устаревший bcrypt напрямую в БД.
    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one()
    user.password_hash = _bcrypt_hash(password)
    await db_session.commit()
    # Отвязываем от сессии, чтобы следующий логин получил свежие данные.
    db_session.expunge_all()

    login = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()

    # После логина хэш должен стать argon2.
    user_after = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one()
    assert is_argon2_hash(user_after.password_hash)


async def test_consent_grant_and_revoke_writes_audit_events(
    client, db_session: AsyncSession
):
    # grant
    grant = await client.post(
        f"{CONSENT_PREFIX}/",
        json={"consent_type": "analytics_tracking"},
    )
    assert grant.status_code == 200

    # revoke
    revoke = await client.delete(
        f"{CONSENT_PREFIX}/analytics_tracking",
    )
    assert revoke.status_code == 200

    events = await _event_types(db_session)
    assert "consent_granted" in events
    assert "consent_revoked" in events