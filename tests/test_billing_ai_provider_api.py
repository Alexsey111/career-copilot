"""Тесты PATCH /me/billing/subscription (ai_provider, #37 DeepSeek).

Подмножество биллинга: меняем только ``ai_provider``. План/статус
управляются Stripe webhook, не пользователем — здесь не покрываем.
"""

from __future__ import annotations

import pytest

from app.models import Subscription
from app.repositories.subscription_repository import SubscriptionRepository


@pytest.mark.asyncio
async def test_get_subscription_returns_default_ai_provider(client, test_user):
    """Free-tier пользователь без Subscription → ``ai_provider=="default"``."""
    resp = await client.get("/api/v1/me/billing/subscription")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_provider"] == "default"


@pytest.mark.asyncio
async def test_patch_ai_provider_creates_subscription_for_free_user(
    client, test_user, db_session
):
    """PATCH ai_provider="deepseek" для free-пользователя создаёт Subscription
    (без Stripe) и сохраняет override."""
    resp = await client.patch(
        "/api/v1/me/billing/subscription",
        json={"ai_provider": "deepseek"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_provider"] == "deepseek"

    sub = await SubscriptionRepository().get_or_none(
        db_session, user_id=test_user.id
    )
    assert sub is not None
    assert sub.ai_provider == "deepseek"
    assert sub.plan == "free"


@pytest.mark.asyncio
async def test_patch_ai_provider_updates_existing_subscription(
    client, test_user, db_session
):
    repo = SubscriptionRepository()
    sub = await repo.create(
        db_session,
        user_id=test_user.id,
        plan="free",
        status="active",
        ai_provider="openai",
    )
    await db_session.flush()

    resp = await client.patch(
        "/api/v1/me/billing/subscription",
        json={"ai_provider": "deepseek"},
    )
    assert resp.status_code == 200, resp.text

    refreshed = await repo.get_or_none(db_session, user_id=test_user.id)
    assert refreshed is not None
    assert refreshed.id == sub.id
    assert refreshed.ai_provider == "deepseek"


@pytest.mark.asyncio
async def test_patch_ai_provider_default_clears_override(
    client, test_user, db_session
):
    repo = SubscriptionRepository()
    await repo.create(
        db_session,
        user_id=test_user.id,
        plan="free",
        status="active",
        ai_provider="deepseek",
    )
    await db_session.flush()

    resp = await client.patch(
        "/api/v1/me/billing/subscription",
        json={"ai_provider": "default"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_provider"] == "default"

    refreshed = await repo.get_or_none(db_session, user_id=test_user.id)
    assert refreshed is not None
    assert refreshed.ai_provider is None


@pytest.mark.asyncio
async def test_patch_ai_provider_rejects_unknown_value(client, test_user):
    """Вне whitelist ``UserAIProvider`` → 422 (Pydantic validation)."""
    resp = await client.patch(
        "/api/v1/me/billing/subscription",
        json={"ai_provider": "gpt-5-fake"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_ai_provider_rejects_mock_value(client, test_user):
    """``mock`` исключён сознательно (test infra, не user-facing)."""
    resp = await client.patch(
        "/api/v1/me/billing/subscription",
        json={"ai_provider": "mock"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_get_subscription_reflects_persisted_ai_provider(
    client, test_user, db_session
):
    """После PATCH ``ai_provider="openai"`` — GET возвращает ``"openai"``."""
    await client.patch(
        "/api/v1/me/billing/subscription",
        json={"ai_provider": "openai"},
    )
    resp = await client.get("/api/v1/me/billing/subscription")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_provider"] == "openai"


@pytest.mark.asyncio
async def test_create_subscription_accepts_ai_provider(
    db_session, test_user
):
    """Регрессия: ``SubscriptionRepository.create()`` должен принимать
    ``ai_provider``. До фикса — PATCH для free-пользователя без Subscription
    падал с TypeError на ``create()``."""
    from app.repositories.subscription_repository import SubscriptionRepository

    sub = await SubscriptionRepository().create(
        db_session,
        user_id=test_user.id,
        plan="free",
        status="active",
        ai_provider="deepseek",
    )
    await db_session.flush()

    assert sub.ai_provider == "deepseek"
