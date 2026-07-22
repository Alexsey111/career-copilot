# tests/test_telegram_linking.py

"""Тесты привязки Telegram-identity (Этап 5, §3.1): HMAC link-token,
web-эндпоинты /me/telegram/*, webhook /start-линковка, webhook-secret verify.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.dependencies import get_telegram_client
from app.core.config import get_settings
from app.main import app
from app.models import AuthEvent, User
from app.repositories.user_repository import UserRepository
from app.services.telegram_link_service import TelegramLinkService
from factories.fake_telegram import FakeTelegramClient
from factories.telegram_updates import make_message_update, make_start_update


# --- HMAC link-token (stateless) ---


def test_link_token_roundtrip(db_session, test_user):
    svc = TelegramLinkService()
    token = svc.generate_link_token(test_user.id)
    assert token.startswith("tg:")
    assert token.count(".") == 1
    user_id = svc.verify_link_token(token)
    assert user_id == test_user.id


def test_link_token_tampered_signature_rejected():
    svc = TelegramLinkService()
    token = svc.generate_link_token(_uuid())
    payload, _sig = token.rsplit(".", 1)
    tampered = payload + "." + "0" * 64
    assert svc.verify_link_token(tampered) is None


def test_link_token_tampered_user_id_rejected():
    svc = TelegramLinkService()
    token = svc.generate_link_token(_uuid())
    payload, sig = token.rsplit(".", 1)
    parts = payload.split(":")
    parts[1] = _uuid().hex
    tampered = ":".join(parts) + "." + sig
    assert svc.verify_link_token(tampered) is None


def test_link_token_expired_rejected(monkeypatch):
    svc = TelegramLinkService()
    token = svc.generate_link_token(_uuid())
    payload, sig = token.rsplit(".", 1)
    parts = payload.split(":")
    # Сдвигаем timestamp далеко в прошлое (> TTL).
    old_ts = str(int(time.time()) - 10_000)
    parts[2] = old_ts
    expired = ":".join(parts) + "." + sig
    assert svc.verify_link_token(expired) is None


def test_link_token_empty():
    assert TelegramLinkService().verify_link_token("") is None


def test_build_deep_link_format():
    svc = TelegramLinkService()
    token = svc.generate_link_token(_uuid())
    link = svc.build_deep_link(token)
    assert str(link).startswith("https://t.me/career_copilot_test_bot?start=")
    assert str(link).endswith(token)


def _uuid():
    from uuid import uuid4

    return uuid4()


# --- /start linking through the service ---


async def _link_via_service(session, user, *, chat_id=111):
    svc = TelegramLinkService()
    updated = await svc.link_user(
        session, user_id=user.id, chat_id=str(chat_id), username="tester"
    )
    await session.commit()
    return updated


@pytest.mark.asyncio
async def test_link_user_persists_chat_id(db_session, test_user):
    await _link_via_service(db_session, test_user, chat_id=111)
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_chat_id == "111"
    assert refreshed.telegram_username == "tester"
    assert refreshed.telegram_linked_at is not None


@pytest.mark.asyncio
async def test_link_user_reassign_clears_previous(db_session, test_user):
    # Первый user привязывает chat_id=222.
    await _link_via_service(db_session, test_user, chat_id=222)
    first = await UserRepository().get_by_id(db_session, test_user.id)
    assert first.telegram_chat_id == "222"

    # Второй user привязывает тот же chat_id → первый отвязывается.
    second_user = User(email=f"second-{test_user.id}@local.test", auth_provider="test")
    db_session.add(second_user)
    await db_session.flush()
    await _link_via_service(db_session, second_user, chat_id=222)

    first_refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert first_refreshed.telegram_chat_id is None
    assert first_refreshed.telegram_dispatch_enabled is False
    second_refreshed = await UserRepository().get_by_id(db_session, second_user.id)
    assert second_refreshed.telegram_chat_id == "222"


@pytest.mark.asyncio
async def test_unlink_clears_fields(db_session, test_user):
    await _link_via_service(db_session, test_user, chat_id=333)
    svc = TelegramLinkService()
    await svc.unlink(db_session, user_id=test_user.id)
    await db_session.commit()
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_chat_id is None
    assert refreshed.telegram_username is None
    assert refreshed.telegram_linked_at is None
    assert refreshed.telegram_dispatch_enabled is False


@pytest.mark.asyncio
async def test_get_by_telegram_chat_id_lookup(db_session, test_user):
    await _link_via_service(db_session, test_user, chat_id=444)
    found = await UserRepository().get_by_telegram_chat_id(db_session, "444")
    assert found is not None
    assert found.id == test_user.id
    missing = await UserRepository().get_by_telegram_chat_id(db_session, "999")
    assert missing is None


# --- /start linking through the webhook (HTTP) ---


@pytest.fixture
def fake_telegram(client):
    fake = FakeTelegramClient()
    app.dependency_overrides[get_telegram_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_telegram_client, None)


@pytest.mark.asyncio
async def test_webhook_start_links_via_http(client, fake_telegram, test_user, db_session):
    token = TelegramLinkService().generate_link_token(test_user.id)
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_start_update(token, chat_id=555)),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    # chat_id persisted.
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_chat_id == "555"
    # Бот ответил сообщением об успешной привязке.
    assert fake_telegram.send_message_calls
    _chat, text = fake_telegram.send_message_calls[0]
    assert "привязан" in text.lower()
    # Audit event.
    events = (
        await db_session.execute(
            select(AuthEvent).where(AuthEvent.event_type == "telegram_link")
        )
    ).scalars().all()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_webhook_start_expired_token_replies_error(client, fake_telegram, test_user, db_session):
    svc = TelegramLinkService()
    token = svc.generate_link_token(test_user.id)
    payload, sig = token.rsplit(".", 1)
    parts = payload.split(":")
    parts[2] = str(int(time.time()) - 10_000)
    expired = ":".join(parts) + "." + sig

    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_start_update(expired, chat_id=5)),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    _chat, text = fake_telegram.send_message_calls[0]
    assert "недействительна" in text.lower() or "истекла" in text.lower()
    # Не привязано.
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_chat_id is None


@pytest.mark.asyncio
async def test_webhook_start_without_token_replies_help(client, fake_telegram, test_user):
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_message_update("/start", chat_id=6)),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    _chat, text = fake_telegram.send_message_calls[0]
    assert "привязк" in text.lower() or "ссылк" in text.lower()


@pytest.mark.asyncio
async def test_webhook_relink_same_token_idempotent(client, fake_telegram, test_user, db_session):
    token = TelegramLinkService().generate_link_token(test_user.id)
    for _ in range(2):
        resp = await client.post(
            "/webhooks/telegram",
            content=json.dumps(make_start_update(token, chat_id=777)),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 200
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_chat_id == "777"


# --- web endpoints ---


@pytest.mark.asyncio
async def test_post_link_returns_deep_link(client, test_user):
    resp = await client.post("/api/v1/me/telegram/link")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["expires_in_minutes"] == get_settings().telegram_link_token_ttl_minutes
    assert body["deep_link"].startswith("https://t.me/career_copilot_test_bot?start=tg:")


@pytest.mark.asyncio
async def test_post_link_503_without_bot_username(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "")
    get_settings.cache_clear()
    try:
        resp = await client.post("/api/v1/me/telegram/link")
        assert resp.status_code == 503, resp.text
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_status_unlinked_then_linked(client, test_user, db_session):
    resp = await client.get("/api/v1/me/telegram/status")
    assert resp.status_code == 200
    assert resp.json()["linked"] is False
    assert resp.json()["dispatch_enabled"] is False

    await _link_via_service(db_session, test_user, chat_id=888)
    resp = await client.get("/api/v1/me/telegram/status")
    assert resp.json()["linked"] is True
    assert resp.json()["chat_id"] == "888"


@pytest.mark.asyncio
async def test_unlink_endpoint(client, test_user, db_session):
    await _link_via_service(db_session, test_user, chat_id=999)
    resp = await client.delete("/api/v1/me/telegram/link")
    assert resp.status_code == 200, resp.text
    assert resp.json()["linked"] is False
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_chat_id is None


@pytest.mark.asyncio
async def test_dispatch_toggle_requires_link(client, test_user):
    resp = await client.patch(
        "/api/v1/me/telegram/dispatch", json={"dispatch_enabled": True}
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_dispatch_toggle_after_link(client, test_user, db_session):
    await _link_via_service(db_session, test_user, chat_id=101)
    resp = await client.patch(
        "/api/v1/me/telegram/dispatch", json={"dispatch_enabled": True}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["dispatch_enabled"] is True
    refreshed = await UserRepository().get_by_id(db_session, test_user.id)
    assert refreshed.telegram_dispatch_enabled is True


# --- webhook secret ---


@pytest.mark.asyncio
async def test_webhook_403_wrong_secret(client, fake_telegram, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
    get_settings.cache_clear()
    try:
        resp = await client.post(
            "/webhooks/telegram",
            content=json.dumps(make_message_update("/help")),
            headers={
                "content-type": "application/json",
                "x-telegram-bot-api-secret-token": "wrong",
            },
        )
        assert resp.status_code == 403, resp.text
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_webhook_200_correct_secret(client, fake_telegram, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
    get_settings.cache_clear()
    try:
        resp = await client.post(
            "/webhooks/telegram",
            content=json.dumps(make_message_update("/help")),
            headers={
                "content-type": "application/json",
                "x-telegram-bot-api-secret-token": "s3cr3t",
            },
        )
        assert resp.status_code == 200, resp.text
        assert fake_telegram.send_message_calls
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_webhook_invalid_json_400(client, fake_telegram):
    resp = await client.post(
        "/webhooks/telegram",
        content="not-json{",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400, resp.text