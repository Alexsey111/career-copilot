# app\services\auth_service.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthEvent, RefreshSession, User
from app.schemas.auth import TokenResponse
from app.security.tokens import (
    create_access_token,
    generate_refresh_token,
    get_refresh_expires,
    hash_refresh_token,
)


LOGIN_FAILED_WINDOW_MINUTES = 15
LOGIN_FAILED_EMAIL_LIMIT = 5
LOGIN_FAILED_IP_LIMIT = 20


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def log_auth_event(
    session: AsyncSession,
    *,
    event_type: str,
    request: Request,
    user_id: Any = None,
    email: str | None = None,
    meta: dict | None = None,
) -> None:
    session.add(
        AuthEvent(
            user_id=user_id,
            event_type=event_type,
            email=email.lower() if email else None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            meta_json=meta or {},
        )
    )


async def get_session_by_token_hash(
    session: AsyncSession,
    token_hash: str,
) -> RefreshSession | None:
    result = await session.execute(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash)
    )
    return result.scalars().first()


async def revoke_all_user_sessions(
    session: AsyncSession,
    user_id: Any,
) -> None:
    result = await session.execute(
        select(RefreshSession).where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
    )
    now = utcnow()
    for refresh_session in result.scalars().all():
        refresh_session.revoked_at = now


def get_password_reset_expires() -> datetime:
    return utcnow() + timedelta(hours=1)


async def issue_tokens(
    session: AsyncSession,
    user: User,
    request: Request,
) -> TokenResponse:
    access_token = create_access_token(str(user.id))
    refresh_plain = generate_refresh_token()
    refresh_hash = hash_refresh_token(refresh_plain)

    refresh_session = RefreshSession(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=get_refresh_expires(),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(refresh_session)
    await session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_plain,
    )


async def count_recent_failed_logins(
    session: AsyncSession,
    *,
    email: str | None,
    ip_address: str | None,
) -> tuple[int, int]:
    since = utcnow() - timedelta(minutes=LOGIN_FAILED_WINDOW_MINUTES)

    email_count = 0
    ip_count = 0

    if email:
        result = await session.execute(
            select(AuthEvent).where(
                AuthEvent.event_type == "login_failed",
                AuthEvent.email == email.lower(),
                AuthEvent.created_at >= since,
            )
        )
        email_count = len(result.scalars().all())

    if ip_address:
        result = await session.execute(
            select(AuthEvent).where(
                AuthEvent.event_type == "login_failed",
                AuthEvent.ip_address == ip_address,
                AuthEvent.created_at >= since,
            )
        )
        ip_count = len(result.scalars().all())

    return email_count, ip_count


async def enforce_login_throttle(
    session: AsyncSession,
    *,
    request: Request,
    email: str,
) -> None:
    ip_address = request.client.host if request.client else None

    email_count, ip_count = await count_recent_failed_logins(
        session,
        email=email,
        ip_address=ip_address,
    )

    if email_count >= LOGIN_FAILED_EMAIL_LIMIT or ip_count >= LOGIN_FAILED_IP_LIMIT:
        await log_auth_event(
            session,
            event_type="login_throttled",
            request=request,
            email=email,
            meta={
                "email_failed_count": email_count,
                "ip_failed_count": ip_count,
                "window_minutes": LOGIN_FAILED_WINDOW_MINUTES,
            },
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )