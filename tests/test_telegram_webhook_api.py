# tests/test_telegram_webhook_api.py

"""E2e webhook через HTTP (Этап 5): secret verify, JSON-parse, нелинкованные
команды → «не привязан», /help через full HTTP path.

Привязка через /start покрывается в ``test_telegram_linking.py``; здесь —
командный path без привязки (не требует seed вакансий/профиля).
"""

from __future__ import annotations

import json

import pytest

from app.api.dependencies import get_telegram_client
from app.main import app
from factories.fake_telegram import FakeTelegramClient
from factories.telegram_updates import make_message_update, make_callback_update


@pytest.fixture
def fake_telegram(client):
    fake = FakeTelegramClient()
    app.dependency_overrides[get_telegram_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_telegram_client, None)


@pytest.mark.asyncio
async def test_webhook_help_full_http_path(client, fake_telegram):
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_message_update("/help", chat_id=42)),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert fake_telegram.send_message_calls
    _chat, text = fake_telegram.send_message_calls[0]
    assert "42" == _chat
    assert "/summary" in text


@pytest.mark.asyncio
async def test_webhook_summary_unlinked_replies_not_linked(client, fake_telegram):
    # chat_id 42 не привязан ни к какому user → «не привязан».
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_message_update("/summary", chat_id=42)),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    _chat, text = fake_telegram.send_message_calls[0]
    assert "привязан" in text.lower()


@pytest.mark.asyncio
async def test_webhook_callback_query_ignored(client, fake_telegram):
    # callback-query v1 не поддерживается → None → 200 ok, без send.
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_callback_update("/summary")),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert fake_telegram.send_message_calls == []


@pytest.mark.asyncio
async def test_webhook_non_object_payload_400(client, fake_telegram):
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps([1, 2, 3]),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_webhook_empty_body_400(client, fake_telegram):
    resp = await client.post(
        "/webhooks/telegram",
        content=b"",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_webhook_send_error_does_not_500(client, fake_telegram):
    # /help требует отправки ответа; если TelegramClient падает — webhook
    # откатывает транзакцию и возвращает 200 (Telegram не ретраит), не 500.
    from factories.fake_telegram import telegram_api_error

    fake_telegram.send_error = telegram_api_error(400, "chat blocked")
    resp = await client.post(
        "/webhooks/telegram",
        content=json.dumps(make_message_update("/help", chat_id=42)),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200, resp.text