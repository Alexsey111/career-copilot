# app\repositories\subscription_repository.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription

# Sentinel: «поле не передано» (не трогать). ``None`` — валидное значение
# («сбросить в NULL»), т.к. подписка может терять customer_id/period_end/canceled_at
# (отмена, реактивация, re-checkout без customer_id). Без sentinel гварды
# ``if x is not None`` делали бы сброс в None невозможным.
_UNSET: Any = object()


class SubscriptionRepository:
    """Репозиторий подписок (Этап 4). Одна запись на пользователя
    (``UniqueConstraint(user_id)``). Пользователь без записи трактуется как
    ``free`` (in-memory view в сервисе) — метод ``get_or_none`` возвращает None.
    """

    async def get_or_none(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        plan: str,
        status: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_end: datetime | None = None,
        canceled_at: datetime | None = None,
        metadata_json: dict | None = None,
        ai_provider: str | None = None,
    ) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            plan=plan,
            status=status,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            current_period_end=current_period_end,
            canceled_at=canceled_at,
            metadata_json=metadata_json or {},
            ai_provider=ai_provider,
        )
        session.add(subscription)
        await session.flush()
        await session.refresh(subscription)
        return subscription

    async def update(
        self,
        session: AsyncSession,
        subscription: Subscription,
        *,
        plan: str | None = _UNSET,
        status: str | None = _UNSET,
        stripe_customer_id: str | None = _UNSET,
        stripe_subscription_id: str | None = _UNSET,
        current_period_end: datetime | None = _UNSET,
        canceled_at: datetime | None = _UNSET,
        metadata_json: dict | None = _UNSET,
        ai_provider: str | None = _UNSET,
    ) -> Subscription:
        if plan is not _UNSET:
            subscription.plan = plan
        if status is not _UNSET:
            subscription.status = status
        if stripe_customer_id is not _UNSET:
            subscription.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not _UNSET:
            subscription.stripe_subscription_id = stripe_subscription_id
        if current_period_end is not _UNSET:
            subscription.current_period_end = current_period_end
        if canceled_at is not _UNSET:
            subscription.canceled_at = canceled_at
        if metadata_json is not _UNSET:
            subscription.metadata_json = metadata_json
        if ai_provider is not _UNSET:
            subscription.ai_provider = ai_provider
        await session.flush()
        await session.refresh(subscription)
        return subscription

    async def get_by_stripe_subscription_id(
        self,
        session: AsyncSession,
        *,
        stripe_subscription_id: str,
    ) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()