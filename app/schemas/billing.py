# app\schemas\billing.py

"""Pydantic-схемы биллинга (Этап 4 — Billing/Stripe, ТЗ §3.5)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class CheckoutResponse(StrictBaseModel):
    checkout_session_id: str = Field(..., min_length=1)
    checkout_url: str = Field(..., min_length=1)


class PortalResponse(StrictBaseModel):
    portal_url: str = Field(..., min_length=1)


class PlanUsageItem(StrictBaseModel):
    action: str
    used: int = Field(..., ge=0)
    limit: int | None = Field(default=None, ge=0)
    window_days: int = Field(..., ge=1)


class MySubscriptionResponse(StrictBaseModel):
    user_id: UUID
    plan: str
    status: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: str | None = None
    canceled_at: str | None = None
    usage: list[PlanUsageItem] = Field(default_factory=list)


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