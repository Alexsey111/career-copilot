# tests\test_billing_webhook.py

"""Тесты Stripe webhook (Этап 4): lifecycle подписки + idempotency.

Webhook без auth (подпись verified через StripeClient). Тесты подменяют
``get_stripe_client`` фейком, парсящим raw JSON-payload.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
import stripe
from sqlalchemy import select

from app.api.dependencies import get_stripe_client
from app.domain.billing import (
    PLAN_PAID_MONTHLY,
    SUBSCRIPTION_ACTIVE,
    SUBSCRIPTION_CANCELED,
    SUBSCRIPTION_PAST_DUE,
)
from app.main import app
from app.models import BillingEvent, Subscription
from factories.fake_stripe import FakeStripeClient
from factories.stripe_events import (
    build_checkout_completed_event,
    build_invoice_event,
    build_subscription_deleted_event,
    build_subscription_updated_event,
    build_unknown_event,
)


@pytest.fixture
def fake_stripe(client):
    fake = FakeStripeClient()
    app.dependency_overrides[get_stripe_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_stripe_client, None)


async def _post_webhook(client, event: dict):
    return await client.post(
        "/webhooks/stripe",
        content=json.dumps(event),
        headers={"stripe-signature": "t=test,v1=fake", "content-type": "application/json"},
    )


@pytest.mark.asyncio
async def test_checkout_completed_persists_subscription(db_session, test_user, fake_stripe):
    # Прямой вызов сервиса (без HTTP) для проверки персистентности.
    from app.services.billing_service import BillingService

    event = build_checkout_completed_event(
        user_id=test_user.id, customer_id="cus_test_1", subscription_id="sub_test_1"
    )
    service = BillingService(stripe_client=fake_stripe)
    result = await service.handle_webhook_event(db_session, event=event)
    await db_session.commit()

    assert result["processed"] is True
    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.plan == PLAN_PAID_MONTHLY
    assert sub.status == SUBSCRIPTION_ACTIVE
    assert sub.stripe_customer_id == "cus_test_1"
    assert sub.stripe_subscription_id == "sub_test_1"
    assert sub.current_period_end is not None

    events = (
        await db_session.execute(select(BillingEvent).where(BillingEvent.stripe_event_id == event["id"]))
    ).scalars().all()
    assert len(events) == 1
    assert events[0].processed is True


@pytest.mark.asyncio
async def test_webhook_idempotent_duplicate(db_session, test_user, fake_stripe):
    from app.services.billing_service import BillingService

    event = build_checkout_completed_event(user_id=test_user.id, event_id="evt_dup_1")
    service = BillingService(stripe_client=fake_stripe)
    first = await service.handle_webhook_event(db_session, event=event)
    await db_session.commit()
    assert first["duplicate"] is False

    second = await service.handle_webhook_event(db_session, event=event)
    assert second["duplicate"] is True
    assert second["processed"] is True

    # Только одна запись billing_event и одна subscription.
    events = (await db_session.execute(select(BillingEvent))).scalars().all()
    assert len(events) == 1
    subs = (await db_session.execute(select(Subscription))).scalars().all()
    assert len(subs) == 1


@pytest.mark.asyncio
async def test_subscription_updated_changes_status(db_session, test_user, fake_stripe):
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    # Сначала checkout → создаёт подписку.
    await service.handle_webhook_event(
        db_session,
        event=build_checkout_completed_event(
            user_id=test_user.id, subscription_id="sub_x", event_id="evt_1"
        ),
    )
    await db_session.commit()

    # past_due через subscription.updated.
    await service.handle_webhook_event(
        db_session,
        event=build_subscription_updated_event(
            subscription_id="sub_x", status="past_due", event_id="evt_2"
        ),
    )
    await db_session.commit()

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.status == SUBSCRIPTION_PAST_DUE


@pytest.mark.asyncio
async def test_subscription_deleted_marks_canceled(db_session, test_user, fake_stripe):
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    await service.handle_webhook_event(
        db_session,
        event=build_checkout_completed_event(
            user_id=test_user.id, subscription_id="sub_x", event_id="evt_1"
        ),
    )
    await db_session.commit()

    await service.handle_webhook_event(
        db_session,
        event=build_subscription_deleted_event(subscription_id="sub_x", event_id="evt_2"),
    )
    await db_session.commit()

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.status == SUBSCRIPTION_CANCELED
    assert sub.canceled_at is not None
    # Период сброшен при удалении подписки (sentinel-aware update).
    assert sub.current_period_end is None


@pytest.mark.asyncio
async def test_subscription_updated_to_canceled_sets_canceled_at(
    db_session, test_user, fake_stripe
):
    """``customer.subscription.updated`` со status=canceled (без отдельного
    ``deleted``) фиксирует ``canceled_at=now`` (находка QA #5)."""
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    await service.handle_webhook_event(
        db_session,
        event=build_checkout_completed_event(
            user_id=test_user.id, subscription_id="sub_x", event_id="evt_1"
        ),
    )
    await db_session.commit()

    # Активная подписка → canceled через subscription.updated (не deleted).
    await service.handle_webhook_event(
        db_session,
        event=build_subscription_updated_event(
            subscription_id="sub_x", status="canceled", event_id="evt_2"
        ),
    )
    await db_session.commit()

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.status == SUBSCRIPTION_CANCELED
    assert sub.canceled_at is not None


@pytest.mark.asyncio
async def test_subscription_reactivated_clears_canceled_at(
    db_session, test_user, fake_stripe
):
    """Возврат в active через subscription.updated сбрасывает ``canceled_at``
    (реактивация). Sentinel-aware update позволяет сброс в NULL."""
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    await service.handle_webhook_event(
        db_session,
        event=build_checkout_completed_event(
            user_id=test_user.id, subscription_id="sub_x", event_id="evt_1"
        ),
    )
    await db_session.commit()
    # Отмена.
    await service.handle_webhook_event(
        db_session,
        event=build_subscription_updated_event(
            subscription_id="sub_x", status="canceled", event_id="evt_2"
        ),
    )
    await db_session.commit()
    # Реактивация.
    await service.handle_webhook_event(
        db_session,
        event=build_subscription_updated_event(
            subscription_id="sub_x", status="active", event_id="evt_3"
        ),
    )
    await db_session.commit()

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.status == SUBSCRIPTION_ACTIVE
    assert sub.canceled_at is None


@pytest.mark.asyncio
async def test_invoice_payment_succeeded_activates(db_session, test_user, fake_stripe):
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    await service.handle_webhook_event(
        db_session,
        event=build_checkout_completed_event(
            user_id=test_user.id, subscription_id="sub_x", event_id="evt_1"
        ),
    )
    await db_session.commit()

    await service.handle_webhook_event(
        db_session,
        event=build_invoice_event(subscription_id="sub_x", succeeded=True, event_id="evt_2"),
    )
    await db_session.commit()

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.status == SUBSCRIPTION_ACTIVE


@pytest.mark.asyncio
async def test_invoice_payment_failed_marks_past_due(db_session, test_user, fake_stripe):
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    await service.handle_webhook_event(
        db_session,
        event=build_checkout_completed_event(
            user_id=test_user.id, subscription_id="sub_x", event_id="evt_1"
        ),
    )
    await db_session.commit()

    await service.handle_webhook_event(
        db_session,
        event=build_invoice_event(subscription_id="sub_x", succeeded=False, event_id="evt_2"),
    )
    await db_session.commit()

    sub = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == test_user.id))
    ).scalar_one()
    assert sub.status == SUBSCRIPTION_PAST_DUE


@pytest.mark.asyncio
async def test_unknown_event_ignored(db_session, test_user, fake_stripe):
    from app.services.billing_service import BillingService

    service = BillingService(stripe_client=fake_stripe)
    result = await service.handle_webhook_event(
        db_session, event=build_unknown_event(event_id="evt_unknown_1")
    )
    await db_session.commit()

    assert result["processed"] is True
    # unknown event не создаёт подписку.
    subs = (await db_session.execute(select(Subscription))).scalars().all()
    assert len(subs) == 0
    events = (await db_session.execute(select(BillingEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].processed is True


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(client, fake_stripe):
    fake_stripe.construct_error = stripe.error.SignatureVerificationError("bad sig", "x")
    resp = await client.post(
        "/webhooks/stripe",
        content=json.dumps({"id": "evt_1", "type": "x", "data": {"object": {}}}),
        headers={"stripe-signature": "v1=fake"},
    )
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_event_missing_id_returns_400(client, fake_stripe):
    resp = await _post_webhook(client, {"type": "checkout.session.completed", "data": {"object": {}}})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_checkout_completed_via_http_persists(
    client, fake_stripe, test_user, db_session
):
    event = build_checkout_completed_event(
        user_id=test_user.id, customer_id="cus_http", subscription_id="sub_http"
    )
    resp = await _post_webhook(client, event)
    assert resp.status_code == 200, resp.text
    assert resp.json()["processed"] is True

    # Проверка через GET /me/billing/subscription.
    sub_resp = await client.get("/api/v1/me/billing/subscription")
    assert sub_resp.status_code == 200
    body = sub_resp.json()
    assert body["plan"] == "paid_monthly"
    assert body["stripe_customer_id"] == "cus_http"
    assert body["stripe_subscription_id"] == "sub_http"