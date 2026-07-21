# tests\test_billing_checkout_portal.py

"""Тесты checkout/portal/me-subscription эндпоинтов (Этап 4)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.api.dependencies import get_stripe_client
from app.domain.billing import PLAN_PAID_MONTHLY, SUBSCRIPTION_ACTIVE
from app.models import Subscription
from app.main import app
from factories.fake_stripe import FakeStripeClient


@pytest.fixture
def fake_stripe(client):
    fake = FakeStripeClient()
    app.dependency_overrides[get_stripe_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_stripe_client, None)


@pytest.mark.asyncio
async def test_checkout_returns_url_and_client_ref(client, fake_stripe, test_user):
    resp = await client.post("/api/v1/billing/checkout")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkout_url"].startswith("https://checkout.stripe.com/test/")
    assert body["checkout_session_id"].startswith("cs_test_")
    # client_reference_id = user_id (для webhook-связи).
    assert fake_stripe.checkout_calls[0]["client_reference_id"] == str(test_user.id)
    assert fake_stripe.checkout_calls[0]["customer_email"] == test_user.email


@pytest.mark.asyncio
async def test_checkout_503_when_price_not_configured(client, test_user, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PAID_MONTHLY_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    # Fresh StripeClient без price_id; сервис проверяет settings.
    try:
        resp = await client.post("/api/v1/billing/checkout")
        assert resp.status_code == 503, resp.text
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_portal_404_without_paid_subscription(client, test_user):
    resp = await client.post("/api/v1/billing/portal")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_portal_returns_url_with_customer_id(
    client, fake_stripe, test_user, db_session
):
    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan=PLAN_PAID_MONTHLY,
            status=SUBSCRIPTION_ACTIVE,
            stripe_customer_id="cus_test_1",
            stripe_subscription_id="sub_test_1",
        )
    )
    await db_session.flush()

    resp = await client.post("/api/v1/billing/portal")
    assert resp.status_code == 200, resp.text
    assert resp.json()["portal_url"].startswith("https://billing.stripe.com/test/")
    assert fake_stripe.portal_calls[0]["customer_id"] == "cus_test_1"


@pytest.mark.asyncio
async def test_get_my_subscription_free_default(client, test_user):
    resp = await client.get("/api/v1/me/billing/subscription")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] == "free"
    assert body["status"] == "active"
    assert body["stripe_customer_id"] is None
    assert body["stripe_subscription_id"] is None
    usage = {item["action"]: item for item in body["usage"]}
    assert set(usage) == {"ai_request", "doc_upload", "generated_output"}
    assert usage["ai_request"]["used"] == 0
    assert usage["ai_request"]["limit"] is not None  # free-tier limit


@pytest.mark.asyncio
async def test_get_my_subscription_paid_unlimited(client, test_user, db_session):
    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan=PLAN_PAID_MONTHLY,
            status=SUBSCRIPTION_ACTIVE,
            stripe_customer_id="cus_test_1",
            stripe_subscription_id="sub_test_1",
        )
    )
    await db_session.flush()

    resp = await client.get("/api/v1/me/billing/subscription")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] == "paid_monthly"
    assert body["stripe_customer_id"] == "cus_test_1"
    usage = {item["action"]: item for item in body["usage"]}
    # paid → limit=None (unlimited).
    assert usage["ai_request"]["limit"] is None
    assert usage["doc_upload"]["limit"] is None
    assert usage["generated_output"]["limit"] is None