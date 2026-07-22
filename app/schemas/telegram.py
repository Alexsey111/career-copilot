# app/schemas/telegram.py

"""Pydantic-схемы Telegram companion (Этап 5, ТЗ §3.6)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, HttpUrl

from app.schemas.base import StrictBaseModel


class TelegramLinkResponse(StrictBaseModel):
    deep_link: HttpUrl
    expires_in_minutes: int = Field(..., ge=1)


class TelegramStatusResponse(StrictBaseModel):
    linked: bool
    chat_id: str | None = None
    username: str | None = None
    linked_at: datetime | None = None
    dispatch_enabled: bool


class TelegramDispatchToggleRequest(StrictBaseModel):
    dispatch_enabled: bool


class TelegramWebhookAck(StrictBaseModel):
    """Webhook ack для Telegram — только ``ok``. Метрики proactive-рассылки
    (dispatched/skipped/errors) живут в ``TelegramDispatchResult`` (админ-
    эндпоинт), не в webhook-ответе."""

    ok: bool = True


class TelegramDispatchResult(StrictBaseModel):
    """Результат proactive-рассылки (для ручного POST-эндпоинта админки)."""

    subscribers: int = Field(..., ge=0)
    dispatched: int = Field(..., ge=0)
    skipped: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)