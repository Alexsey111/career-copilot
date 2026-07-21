# app\services\billing_service.py

"""Сервис биллинга (Этап 4 — Billing/Stripe, ТЗ §3.5).

Оркестрирует Stripe-чекаут, billing-portal, чтение подписки и обработку
webhook-событий (с idempotency через ``billing_events``). Зависит от
``StripeClient`` (DI-mockable), репозиториев и ``QuotaService``.

Webhook-события (минимальный жизненный цикл подписки):
- ``checkout.session.completed`` → создаёт/активирует ``Subscription``
  (``client_reference_id`` = user_id).
- ``customer.subscription.updated`` → обновляет status/period_end.
- ``customer.subscription.deleted`` → ``status=canceled``/``ended``.
- ``invoice.payment_succeeded`` → ``status=active`` + ``current_period_end``.
- ``invoice.payment_failed`` → ``status=past_due``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.billing import (
    PLAN_FREE,
    PLAN_PAID_MONTHLY,
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_CANCELED,
    SUBSCRIPTION_ENDED,
    SUBSCRIPTION_PAST_DUE,
)
from app.repositories.billing_event_repository import BillingEventRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.stripe_client import StripeClient


# --- Хелперы для чтения dict-like Stripe-объектов ----------------------------


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """dict-like доступ, совместимый со StripeObject и plain dict."""
    if obj is None:
        return default
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError):
        return getattr(obj, key, default)


def _parse_period_end(value: Any) -> datetime | None:
    """Stripe передаёт ``current_period_end`` как unix-секунды (int)."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _map_subscription_status(stripe_status: Any) -> str:
    """Маппинг статуса Stripe-подписки → наш ``SubscriptionStatus``."""
    s = str(stripe_status or "").lower()
    # Stripe: incomplete, incomplete_expired, trialing, active, past_due,
    # canceled, unpaid, paused. Активный доступ: trialing + active.
    if s in ("active", "trialing"):
        return SUBSCRIPTION_ACTIVE
    if s in ("past_due", "unpaid"):
        return SUBSCRIPTION_PAST_DUE
    if s == "canceled":
        return SUBSCRIPTION_CANCELED
    # incomplete/incomplete_expired/paused/unknown → ended (нет доступа).
    return SUBSCRIPTION_ENDED


class BillingService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        subscription_repository: SubscriptionRepository | None = None,
        event_repository: BillingEventRepository | None = None,
        stripe_client: StripeClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._subscription_repository = (
            subscription_repository or SubscriptionRepository()
        )
        self._event_repository = event_repository or BillingEventRepository()
        self._stripe = stripe_client or StripeClient(settings=self._settings)

    # --- Checkout / Portal / Reading ----------------------------------------

    async def create_checkout_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        user_email: str,
    ) -> dict[str, Any]:
        if not self._settings.stripe_price_paid_monthly_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="billing is not configured (STRIPE_PRICE_PAID_MONTHLY_ID)",
            )
        cs = self._stripe.create_checkout_session(
            customer_email=user_email,
            client_reference_id=str(user_id),
            price_id=self._settings.stripe_price_paid_monthly_id,
            success_url=self._settings.billing_checkout_success_url,
            cancel_url=self._settings.billing_checkout_cancel_url,
        )
        return {
            "checkout_session_id": cs["id"],
            "checkout_url": cs["url"],
        }

    async def create_billing_portal_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        subscription = await self._subscription_repository.get_or_none(
            session, user_id=user_id
        )
        if subscription is None or not subscription.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="no paid subscription found; checkout first",
            )
        ps = self._stripe.create_billing_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=self._settings.billing_portal_return_url,
        )
        return {"portal_url": ps["url"]}

    async def get_my_subscription(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        subscription = await self._subscription_repository.get_or_none(
            session, user_id=user_id
        )
        if subscription is None:
            return {
                "user_id": str(user_id),
                "plan": PLAN_FREE,
                "status": SUBSCRIPTION_ACTIVE,
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
                "current_period_end": None,
                "canceled_at": None,
            }
        return {
            "user_id": str(user_id),
            "plan": subscription.plan,
            "status": subscription.status,
            "stripe_customer_id": subscription.stripe_customer_id,
            "stripe_subscription_id": subscription.stripe_subscription_id,
            "current_period_end": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None
            ),
            "canceled_at": (
                subscription.canceled_at.isoformat()
                if subscription.canceled_at
                else None
            ),
        }

    # --- Webhook -------------------------------------------------------------

    async def handle_webhook_event(
        self,
        session: AsyncSession,
        *,
        event: Any,
    ) -> dict[str, Any]:
        """Обрабатывает одно Stripe-событие идемпотентно.

        ``event`` — dict-like (``["id"]``, ``["type"]``, ``["data"]["object"]``).
        Дедуп: повторный ``stripe_event_id`` с ``processed=True`` → no-op.
        """
        event_id = str(_get(event, "id", ""))
        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="stripe event missing id",
            )
        event_type = str(_get(event, "type", ""))
        obj = _get(_get(event, "data"), "object")

        existing = await self._event_repository.get_by_stripe_event_id(
            session, stripe_event_id=event_id
        )
        if existing is not None and existing.processed:
            return {"processed": True, "duplicate": True, "event_type": event_type}

        subscription_id: UUID | None = None
        error_text: str | None = None
        try:
            subscription_id = await self._dispatch_event(session, event_type, obj)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — логируем в billing_events, не роняем webhook с 5xx без записи
            error_text = f"{type(exc).__name__}: {exc}"

        # Записываем idempotency-лог (создаём, если ещё нет).
        if existing is None:
            billing_event = await self._event_repository.create(
                session,
                stripe_event_id=event_id,
                event_type=event_type,
                subscription_id=subscription_id,
                processed=error_text is None,
                payload_json=self._safe_payload(event),
                error_text=error_text,
            )
            processed = billing_event.processed
        else:
            await self._event_repository.mark_processed(
                session,
                existing,
                subscription_id=subscription_id,
                error_text=error_text,
            )
            processed = error_text is None

        if error_text is not None:
            # Возвращаем 400, чтобы Stripe ретраил после нашей пометки — но
            # запись сохранена (processed=False) для диагностики.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"webhook event processing failed: {error_text}",
            )
        return {"processed": processed, "duplicate": False, "event_type": event_type}

    def _safe_payload(self, event: Any) -> dict[str, Any]:
        """Сохраняет минимум payload для аудита (без ПДн вне customer_id)."""
        try:
            return {
                "id": str(_get(event, "id", "")),
                "type": str(_get(event, "type", "")),
            }
        except Exception:  # noqa: BLE001
            return {}

    async def _dispatch_event(
        self,
        session: AsyncSession,
        event_type: str,
        obj: Any,
    ) -> UUID | None:
        """Маршрутизация по типу события. Возвращает subscription_id (наш)."""
        if event_type == "checkout.session.completed":
            return await self._on_checkout_completed(session, obj)
        if event_type == "customer.subscription.updated":
            return await self._on_subscription_changed(session, obj, deleted=False)
        if event_type == "customer.subscription.deleted":
            return await self._on_subscription_changed(session, obj, deleted=True)
        if event_type == "invoice.payment_succeeded":
            return await self._on_invoice_payment(session, obj, succeeded=True)
        if event_type == "invoice.payment_failed":
            return await self._on_invoice_payment(session, obj, succeeded=False)
        # Неизвестный/ненужный тип — успешно игнорируем (processed=True).
        return None

    async def _on_checkout_completed(
        self,
        session: AsyncSession,
        obj: Any,
    ) -> UUID | None:
        client_ref = str(_get(obj, "client_reference_id", "") or "")
        if not client_ref:
            return None
        try:
            user_id = UUID(client_ref)
        except ValueError:
            return None

        customer_id = _get(obj, "customer")
        subscription_stripe_id = _get(obj, "subscription")
        period_end = _parse_period_end(_get(obj, "current_period_end"))

        # Если period_end не пришёл в checkout — достаём из подписки.
        if period_end is None and subscription_stripe_id:
            try:
                sub = self._stripe.retrieve_subscription(str(subscription_stripe_id))
                period_end = _parse_period_end(sub.get("current_period_end"))
            except Exception:  # noqa: BLE001 — период не критичен для активации
                period_end = None

        subscription = await self._subscription_repository.get_or_none(
            session, user_id=user_id
        )
        if subscription is None:
            subscription = await self._subscription_repository.create(
                session,
                user_id=user_id,
                plan=PLAN_PAID_MONTHLY,
                status=SUBSCRIPTION_ACTIVE,
                stripe_customer_id=str(customer_id) if customer_id else None,
                stripe_subscription_id=(
                    str(subscription_stripe_id) if subscription_stripe_id else None
                ),
                current_period_end=period_end,
            )
        else:
            subscription = await self._subscription_repository.update(
                session,
                subscription,
                plan=PLAN_PAID_MONTHLY,
                status=SUBSCRIPTION_ACTIVE,
                stripe_customer_id=str(customer_id) if customer_id else None,
                stripe_subscription_id=(
                    str(subscription_stripe_id) if subscription_stripe_id else None
                ),
                current_period_end=period_end,
            )
        return subscription.id

    async def _on_subscription_changed(
        self,
        session: AsyncSession,
        obj: Any,
        *,
        deleted: bool,
    ) -> UUID | None:
        stripe_sub_id = _get(obj, "id")
        if not stripe_sub_id:
            return None
        subscription = await self._subscription_repository.get_by_stripe_subscription_id(
            session, stripe_subscription_id=str(stripe_sub_id)
        )
        if subscription is None:
            return None
        if deleted:
            new_status = SUBSCRIPTION_CANCELED
            period_end = None  # сброс периода (sentinel-aware update)
            canceled_at = datetime.now(timezone.utc)
        else:
            new_status = _map_subscription_status(_get(obj, "status"))
            # Сохраняем старый period_end, если Stripe не прислал новый.
            period_end = _parse_period_end(_get(obj, "current_period_end")) or (
                subscription.current_period_end
            )
            if new_status in (SUBSCRIPTION_CANCELED, SUBSCRIPTION_ENDED):
                # canceled_at: сохраняем существующий, иначе фиксируем момент отмены.
                canceled_at = subscription.canceled_at or datetime.now(timezone.utc)
            else:
                # Реактивация (active/past_due) — сбрасываем canceled_at.
                canceled_at = None
        await self._subscription_repository.update(
            session,
            subscription,
            status=new_status,
            current_period_end=period_end,
            canceled_at=canceled_at,
        )
        return subscription.id

    async def _on_invoice_payment(
        self,
        session: AsyncSession,
        obj: Any,
        *,
        succeeded: bool,
    ) -> UUID | None:
        stripe_sub_id = _get(obj, "subscription")
        if not stripe_sub_id:
            return None
        subscription = await self._subscription_repository.get_by_stripe_subscription_id(
            session, stripe_subscription_id=str(stripe_sub_id)
        )
        if subscription is None:
            return None
        if succeeded:
            new_status = SUBSCRIPTION_ACTIVE
            # Сохраняем старый period_end, если Stripe не прислал новый в инвойсе.
            period_end = _parse_period_end(_get(obj, "period_end")) or (
                subscription.current_period_end
            )
        else:
            new_status = SUBSCRIPTION_PAST_DUE
            period_end = subscription.current_period_end
        await self._subscription_repository.update(
            session,
            subscription,
            status=new_status,
            current_period_end=period_end,
        )
        return subscription.id