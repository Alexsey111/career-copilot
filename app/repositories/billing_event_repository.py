# app\repositories\billing_event_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BillingEvent


class BillingEventRepository:
    """Репозиторий idempotency-лога Stripe webhook-событий (Этап 4).

    ``stripe_event_id`` UNIQUE → дедуп ретраев Stripe. Перед обработкой
    webhook'а сервис ищет существующую запись; если уже ``processed=True`` —
    no-op. ``processed=False`` (упавшая попытка) → повторная обработка.
    """

    async def get_by_stripe_event_id(
        self,
        session: AsyncSession,
        *,
        stripe_event_id: str,
    ) -> BillingEvent | None:
        stmt = select(BillingEvent).where(BillingEvent.stripe_event_id == stripe_event_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        *,
        stripe_event_id: str,
        event_type: str,
        subscription_id: UUID | None = None,
        processed: bool = False,
        payload_json: dict | None = None,
        error_text: str | None = None,
    ) -> BillingEvent:
        event = BillingEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            subscription_id=subscription_id,
            processed=processed,
            payload_json=payload_json or {},
            error_text=error_text,
        )
        session.add(event)
        await session.flush()
        await session.refresh(event)
        return event

    async def mark_processed(
        self,
        session: AsyncSession,
        event: BillingEvent,
        *,
        subscription_id: UUID | None = None,
        error_text: str | None = None,
    ) -> BillingEvent:
        event.processed = True
        if subscription_id is not None:
            event.subscription_id = subscription_id
        if error_text is not None:
            event.error_text = error_text
        await session.flush()
        await session.refresh(event)
        return event