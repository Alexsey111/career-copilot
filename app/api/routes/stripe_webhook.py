# app\api\routes\stripe_webhook.py

"""Stripe webhook endpoint (Этап 4 — Billing).

Raw body, без auth (подпись verified через ``stripe.Webhook.construct_event``).
Путь ``/webhooks/stripe`` — регистрируется в ``app/main.py`` БЕЗ api-prefix
(как ``/metrics``), т.к. Stripe шлёт на корневой путь.

Idempotency через ``billing_events`` (``stripe_event_id`` UNIQUE) — ретраи
Stripe не дублируют эффект.
"""

from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_stripe_client
from app.db.session import get_db_session
from app.schemas.billing import WebhookAck
from app.services.billing_service import BillingService
from app.services.stripe_client import StripeClient


router = APIRouter(tags=["billing-webhook"])


@router.post("/webhooks/stripe", response_model=WebhookAck)
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> WebhookAck:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_client.construct_webhook_event(
            payload=payload,
            sig_header=sig_header,
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid stripe signature: {exc}",
        )
    except ValueError as exc:
        # Некорректный payload (не JSON / битый).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid stripe payload: {exc}",
        )

    service = BillingService(stripe_client=stripe_client)
    try:
        result = await service.handle_webhook_event(session, event=event)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return WebhookAck.model_validate(result)