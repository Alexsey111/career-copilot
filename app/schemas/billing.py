# app\schemas\billing.py

"""Pydantic-схемы биллинга (Этап 4 — Billing/Stripe, ТЗ §3.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel

# Per-user LLM-провайдер (#37 DeepSeek). Модель НЕ выбирается пользователем —
# она фиксирована в коде (deepseek-chat, gpt-4o-mini, gigachat-pro). ``None``
# (в БД) трактуется как «использовать settings.ai_provider». На UI PATCH
# принимает Literal-строку, а None передаётся через явный флаг ``"default"``.
# ``mock`` исключён сознательно: production-валидатор ``Settings`` его
# блокирует, а в dev/test — отдельный test client.
UserAIProvider = Literal["gigachat", "openai", "deepseek", "default"]


class CheckoutResponse(StrictBaseModel):
    checkout_session_id: str = Field(..., min_length=1)
    checkout_url: str = Field(..., min_length=1)


class PortalResponse(StrictBaseModel):
    portal_url: str = Field(..., min_length=1)


class PlanUsageItem(StrictBaseModel):
    action: str
    used: int = Field(..., ge=0)
    limit: int | None = Field(default=None, ge=0)
    # Дневное окно — для большинства действий; секундное окно — только для
    # demo-действий (``vacancy_import``). Ровно одно из двух присутствует.
    window_days: int | None = Field(default=None, ge=1)
    window_seconds: int | None = Field(default=None, ge=1)
    # Самая старая запись в текущем окне (UTC). None если used=0.
    # Фронт использует для обратного отсчёта «сброс через X мин» — когда
    # эта запись выйдет за окно, used уменьшится на 1.
    oldest_in_window: Optional[datetime] = None


class MySubscriptionResponse(StrictBaseModel):
    user_id: UUID
    plan: str
    status: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: str | None = None
    canceled_at: str | None = None
    usage: list[PlanUsageItem] = Field(default_factory=list)
    # Per-user override LLM-провайдера. ``"default"`` означает «использовать
    # settings.ai_provider» (т.е. ``Subscription.ai_provider IS NULL``). UI
    # получает строку, бэк маппит ``"default"`` → None при записи.
    ai_provider: str = "default"


class UpdateMySubscriptionRequest(StrictBaseModel):
    """Тело PATCH /me/billing/subscription. Поддерживает только ``ai_provider``
    (выбор LLM-провайдера пользователем, #37 DeepSeek). План/статус
    управляются Stripe-webhook, не пользователем."""

    ai_provider: UserAIProvider


class WebhookAck(StrictBaseModel):
    processed: bool
    duplicate: bool
    event_type: str


class QuotaErrorDetail(StrictBaseModel):
    """Тело 402-ответа при превышении квоты (detail ``require_quota``)."""

    action: str
    plan: str
    used: int = Field(..., ge=0)
    limit: int | None = Field(default=None, ge=0)
    reason: str