# tests\factories\stripe_events.py

"""Фабрики synthetic Stripe-событий для тестов webhook'а (Этап 4).

Возвращают plain-dict'ы в форме Stripe-Event (``{"id", "type", "data":
{"object": {...}}}``). ``BillingService`` читает их через dict-like доступ
(``_get``), совместимый и с plain-dict, и со StripeObject.

period_end — unix-секунды (как у Stripe ``current_period_end``).
"""

from __future__ import annotations

from uuid import uuid4

PERIOD_END_TS = 4102444800  # 2100-01-01T00:00:00Z — стабильное будущее


def _evt(event_type: str, obj: dict, event_id: str | None = None) -> dict:
    return {
        "id": event_id or f"evt_{uuid4().hex}",
        "type": event_type,
        "data": {"object": obj},
    }


def build_checkout_completed_event(
    *,
    user_id,
    customer_id: str = "cus_test_1",
    subscription_id: str = "sub_test_1",
    period_end_ts: int | None = PERIOD_END_TS,
    event_id: str | None = None,
) -> dict:
    obj = {
        "client_reference_id": str(user_id),
        "customer": customer_id,
        "subscription": subscription_id,
    }
    if period_end_ts is not None:
        obj["current_period_end"] = period_end_ts
    return _evt("checkout.session.completed", obj, event_id)


def build_subscription_updated_event(
    *,
    subscription_id: str = "sub_test_1",
    status: str = "active",
    period_end_ts: int | None = PERIOD_END_TS,
    customer_id: str = "cus_test_1",
    event_id: str | None = None,
) -> dict:
    obj = {
        "id": subscription_id,
        "status": status,
        "customer": customer_id,
    }
    if period_end_ts is not None:
        obj["current_period_end"] = period_end_ts
    return _evt("customer.subscription.updated", obj, event_id)


def build_subscription_deleted_event(
    *,
    subscription_id: str = "sub_test_1",
    period_end_ts: int | None = PERIOD_END_TS,
    customer_id: str = "cus_test_1",
    event_id: str | None = None,
) -> dict:
    obj = {
        "id": subscription_id,
        "status": "canceled",
        "customer": customer_id,
        "current_period_end": period_end_ts,
    }
    return _evt("customer.subscription.deleted", obj, event_id)


def build_invoice_event(
    *,
    subscription_id: str = "sub_test_1",
    succeeded: bool = True,
    period_end_ts: int | None = PERIOD_END_TS,
    event_id: str | None = None,
) -> dict:
    obj: dict = {"subscription": subscription_id}
    if period_end_ts is not None:
        obj["period_end"] = period_end_ts
    return _evt(
        "invoice.payment_succeeded" if succeeded else "invoice.payment_failed",
        obj,
        event_id,
    )


def build_unknown_event(*, event_id: str | None = None) -> dict:
    return _evt("product.created", {"id": "prod_test_1"}, event_id)