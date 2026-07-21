# tests\test_billing_encryption.py

"""Тесты шифрования at-rest для биллинга (Этап 4, ФЗ-152 ст.19).

``stripe_customer_id`` — PII/finance → ``EncryptedText``. Проверяем, что в БД
хранится Fernet-ciphertext (raw SELECT не содержит plaintext-маркера), а ORM
расшифровывает при доступе. ``stripe_subscription_id`` — plain String (публичный
Stripe-id) → не шифруется.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.domain.billing import PLAN_PAID_MONTHLY, SUBSCRIPTION_ACTIVE
from app.models import Subscription
from app.repositories.subscription_repository import SubscriptionRepository


@pytest.mark.asyncio
async def test_stripe_customer_id_encrypted_at_rest(db_session, test_user) -> None:
    marker = f"cus_secret_{uuid4().hex}"
    repo = SubscriptionRepository()
    subscription = await repo.create(
        db_session,
        user_id=test_user.id,
        plan=PLAN_PAID_MONTHLY,
        status=SUBSCRIPTION_ACTIVE,
        stripe_customer_id=marker,
        stripe_subscription_id="sub_plain_123",
    )

    # Raw column — must NOT contain the plaintext marker (Fernet base64 at rest).
    raw_customer_id = await db_session.scalar(
        text("SELECT stripe_customer_id FROM subscriptions WHERE id = :id"),
        {"id": str(subscription.id)},
    )
    assert raw_customer_id is not None
    assert marker not in raw_customer_id
    assert "cus_secret_" not in raw_customer_id

    # ORM read — decrypted, contains the marker.
    loaded = (
        await db_session.execute(
            select(Subscription).where(Subscription.id == subscription.id)
        )
    ).scalar_one()
    assert loaded.stripe_customer_id == marker


@pytest.mark.asyncio
async def test_stripe_subscription_id_plain_string(db_session, test_user) -> None:
    """``stripe_subscription_id`` — публичный Stripe-id, НЕ шифруется
    (нужен для webhook lookup без decrypt-оверхеда, не даёт доступа к средствам)."""
    repo = SubscriptionRepository()
    subscription = await repo.create(
        db_session,
        user_id=test_user.id,
        plan=PLAN_PAID_MONTHLY,
        status=SUBSCRIPTION_ACTIVE,
        stripe_customer_id="cus_test_1",
        stripe_subscription_id="sub_public_123",
    )

    raw_sub_id = await db_session.scalar(
        text("SELECT stripe_subscription_id FROM subscriptions WHERE id = :id"),
        {"id": str(subscription.id)},
    )
    # Plain — хранится как есть.
    assert raw_sub_id == "sub_public_123"


@pytest.mark.asyncio
async def test_subscription_unique_per_user(db_session, test_user) -> None:
    """UniqueConstraint(user_id) — вторая подписка того же пользователя невозможна."""
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan="free",
            status="active",
        )
    )
    await db_session.flush()

    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan=PLAN_PAID_MONTHLY,
            status=SUBSCRIPTION_ACTIVE,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_billing_event_stripe_event_id_unique(db_session, test_user) -> None:
    """``stripe_event_id`` UNIQUE — дедуп ретраев Stripe."""
    from sqlalchemy.exc import IntegrityError

    from app.models import BillingEvent

    db_session.add(
        BillingEvent(
            stripe_event_id="evt_unique_1",
            event_type="checkout.session.completed",
            payload_json={},
        )
    )
    await db_session.flush()

    db_session.add(
        BillingEvent(
            stripe_event_id="evt_unique_1",
            event_type="checkout.session.completed",
            payload_json={},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()