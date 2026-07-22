# app\repositories\user_repository.py

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_oauth_provider_id(
        self,
        session: AsyncSession,
        *,
        provider: str,
        provider_id: str,
    ) -> User | None:
        stmt = select(User).where(
            User.auth_provider == provider,
            User.oauth_provider_id == provider_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_telegram_chat_id(
        self,
        session: AsyncSession,
        chat_id: str,
    ) -> User | None:
        """Lookup user по Telegram chat_id (webhook-маршрутизация команд бота).
        ``chat_id`` — plain pseudonymous lookup-key (как ``oauth_provider_id``).
        """
        stmt = select(User).where(User.telegram_chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_telegram_subscribers(
        self,
        session: AsyncSession,
    ) -> list[User]:
        """Активные users с привязанным Telegram и per-user opt-in для
        proactive push (Celery beat ``dispatch_telegram_alerts``)."""
        stmt = select(User).where(
            User.telegram_chat_id.is_not(None),
            User.telegram_dispatch_enabled.is_(True),
            User.is_active.is_(True),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        session: AsyncSession,
        *,
        email: str,
        password_hash: str | None = None,
        auth_provider: str | None = "local",
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            auth_provider=auth_provider,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user
