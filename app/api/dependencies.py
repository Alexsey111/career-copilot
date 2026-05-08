# app\api\dependencies.py

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import create_ai_orchestrator
from app.ai.orchestrator import AIOrchestrator
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models import User
from app.repositories.user_repository import UserRepository
from app.security.dependencies import get_current_active_user


def get_ai_orchestrator() -> AIOrchestrator:
    """FastAPI dependency для получения AI-оркестратора.

    Все endpoint'ы и сервисы, которым нужен AI,
    должны использовать эту dependency вместо прямого вызова factory.
    """
    return create_ai_orchestrator()


async def get_current_dev_user(
    session: AsyncSession = Depends(get_db_session),
) -> User:
    settings = get_settings()

    if not settings.dev_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEV_AUTH_ENABLED is false, but get_current_dev_user() is required",
        )

    if not settings.dev_user_email or not settings.dev_user_email.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEV_USER_EMAIL is not configured",
        )

    email = settings.dev_user_email.strip().lower()
    user_repository = UserRepository()

    user = await user_repository.get_by_email(session, email)
    if user is None:
        user = User(
            email=email,
            auth_provider="dev",
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)

    return user


__all__ = ["get_current_active_user", "get_current_dev_user", "get_ai_orchestrator"]
