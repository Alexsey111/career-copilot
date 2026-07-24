# app\api\routes\billing.py

"""Эндпоинты биллинга (Этап 4 — Billing/Stripe, ТЗ §3.5).

- ``POST /billing/checkout`` — Stripe Checkout Session для перехода на paid.
- ``POST /billing/portal`` — Stripe Billing Portal (управление подпиской).
- ``GET  /me/billing/subscription`` — текущий план + usage.

Webhook живёт отдельно (``app/api/routes/stripe_webhook.py``) — без prefix,
без auth, raw body (signature verified via Stripe).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_stripe_client
from app.db.session import get_db_session
from app.models import User
from app.schemas.billing import (
    CheckoutResponse,
    MySubscriptionResponse,
    PlanUsageItem,
    PortalResponse,
    UpdateMySubscriptionRequest,
)
from app.services.billing_service import BillingService
from app.services.quota_service import QuotaService
from app.services.stripe_client import StripeClient


router = APIRouter(tags=["billing"])


@router.post("/billing/checkout", response_model=CheckoutResponse)
async def create_checkout(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> CheckoutResponse:
    service = BillingService(stripe_client=stripe_client)
    result = await service.create_checkout_session(
        session,
        user_id=current_user.id,
        user_email=current_user.email,
    )
    return CheckoutResponse.model_validate(result)


@router.post("/billing/portal", response_model=PortalResponse)
async def create_portal(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> PortalResponse:
    service = BillingService(stripe_client=stripe_client)
    result = await service.create_billing_portal_session(
        session,
        user_id=current_user.id,
    )
    return PortalResponse.model_validate(result)


@router.get("/me/billing/subscription", response_model=MySubscriptionResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> MySubscriptionResponse:
    billing = BillingService()
    subscription = await billing.get_my_subscription(
        session,
        user_id=current_user.id,
    )
    quota = QuotaService()
    usage_map = await quota.get_usage(session, user_id=current_user.id)
    usage_items = [
        PlanUsageItem(
            action=action,
            used=item["used"],
            limit=item["limit"],
            window_days=item.get("window_days"),
            window_seconds=item.get("window_seconds"),
            oldest_in_window=item.get("oldest_in_window"),
        )
        for action, item in usage_map.items()
    ]
    return MySubscriptionResponse(
        user_id=UUID(subscription["user_id"]),
        plan=subscription["plan"],
        status=subscription["status"],
        stripe_customer_id=subscription["stripe_customer_id"],
        stripe_subscription_id=subscription["stripe_subscription_id"],
        current_period_end=subscription["current_period_end"],
        canceled_at=subscription["canceled_at"],
        usage=usage_items,
        ai_provider=subscription.get("ai_provider", "default"),
    )


@router.patch("/me/billing/subscription", response_model=MySubscriptionResponse)
async def update_my_subscription(
    payload: UpdateMySubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> MySubscriptionResponse:
    """Частичное обновление подписки (только ``ai_provider``, #37 DeepSeek).

    План/статус — не редактируются через этот эндпоинт (источник истины —
    Stripe webhook). ``ai_provider="default"`` сбрасывает override.
    """
    service = BillingService()
    await service.update_ai_provider(
        session,
        user_id=current_user.id,
        ai_provider=payload.ai_provider,
    )
    # Возвращаем полный view (с usage), чтобы UI не делал второй GET.
    subscription = await service.get_my_subscription(
        session, user_id=current_user.id
    )
    quota = QuotaService()
    usage_map = await quota.get_usage(session, user_id=current_user.id)
    usage_items = [
        PlanUsageItem(
            action=action,
            used=item["used"],
            limit=item["limit"],
            window_days=item.get("window_days"),
            window_seconds=item.get("window_seconds"),
            oldest_in_window=item.get("oldest_in_window"),
        )
        for action, item in usage_map.items()
    ]
    return MySubscriptionResponse(
        user_id=UUID(subscription["user_id"]),
        plan=subscription["plan"],
        status=subscription["status"],
        stripe_customer_id=subscription["stripe_customer_id"],
        stripe_subscription_id=subscription["stripe_subscription_id"],
        current_period_end=subscription["current_period_end"],
        canceled_at=subscription["canceled_at"],
        usage=usage_items,
        ai_provider=subscription.get("ai_provider", "default"),
    )