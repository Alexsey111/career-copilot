# app/api/routes/telegram.py

"""Web-эндпоинты Telegram companion (Этап 5, ТЗ §3.6 / §3.1).

Привязка identity и управление proactive push. Под api-prefix ``/api/v1``,
аутентификация + ``require_data_processing_consent`` (привязка chat_id —
обработка ПДн, ФЗ-152). Webhook живёт отдельно
(``app/api/routes/telegram_webhook.py``) — без prefix, без auth.

Эндпоинты грузят реального ``User`` из БД по ``current_user.id`` (DI-зависимость
``get_current_active_user`` в тестах возвращает ``SimpleNamespace`` без
``telegram_*`` полей), а не работают с объектом зависимости напрямую.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_data_processing_consent
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.telegram import (
    TelegramDispatchToggleRequest,
    TelegramLinkResponse,
    TelegramStatusResponse,
)
from app.services.telegram_link_service import TelegramLinkService


router = APIRouter(prefix="/me/telegram", tags=["telegram"])


def _status_for(user: User) -> TelegramStatusResponse:
    return TelegramStatusResponse(
        linked=user.telegram_chat_id is not None,
        chat_id=user.telegram_chat_id,
        username=user.telegram_username,
        linked_at=user.telegram_linked_at,
        dispatch_enabled=user.telegram_dispatch_enabled,
    )


async def _load_user(session: AsyncSession, user_id) -> User:
    user = await UserRepository().get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


@router.post("/link", response_model=TelegramLinkResponse)
async def create_link(
    current_user: User = Depends(require_data_processing_consent),
) -> TelegramLinkResponse:
    """Генерирует HMAC-signed stateless link-token + deep link
    ``https://t.me/<bot>?start=<token>``. Без commit — токен stateless."""
    settings = get_settings()
    if not settings.telegram_bot_username:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEGRAM_BOT_USERNAME is not configured",
        )
    link_service = TelegramLinkService()
    token = link_service.generate_link_token(current_user.id)
    deep_link = link_service.build_deep_link(token)
    return TelegramLinkResponse(
        deep_link=deep_link,
        expires_in_minutes=settings.telegram_link_token_ttl_minutes,
    )


@router.get("/status", response_model=TelegramStatusResponse)
async def get_status(
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> TelegramStatusResponse:
    user = await _load_user(session, current_user.id)
    return _status_for(user)


@router.delete("/link", response_model=TelegramStatusResponse)
async def unlink(
    request: Request,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> TelegramStatusResponse:
    link_service = TelegramLinkService()
    user = await link_service.unlink(session, user_id=current_user.id, request=request)
    await session.commit()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _status_for(user)


@router.patch("/dispatch", response_model=TelegramStatusResponse)
async def toggle_dispatch(
    payload: TelegramDispatchToggleRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> TelegramStatusResponse:
    """Per-user opt-in для proactive push (Celery beat). Требует привязки."""
    user = await _load_user(session, current_user.id)
    if payload.dispatch_enabled and not user.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="link telegram first (POST /me/telegram/link)",
        )
    user.telegram_dispatch_enabled = payload.dispatch_enabled
    await session.commit()
    return _status_for(user)