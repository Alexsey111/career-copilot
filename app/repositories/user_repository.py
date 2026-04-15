# app\repositories\user_repository.py

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        *,
        email: str,
        auth_provider: str | None = "local",
    ) -> User:
        user = User(
            email=email,
            auth_provider=auth_provider,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user