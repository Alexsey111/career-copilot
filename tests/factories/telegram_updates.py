# tests/factories/telegram_updates.py

"""Фабрики synthetic Telegram update-dict'ов для тестов webhook'а (Этап 5).

Возвращают plain-dict'и в форме Telegram Bot API ``Update``. ``message`` —
text-команда, ``callback_query`` — (v1 не обрабатывается, но фабрика есть для
будущего). ``chat_id`` — int (Telegram private chat), в сервисе приводится к
str перед lookup/отправкой.
"""

from __future__ import annotations

from typing import Any


def make_message_update(
    text: str,
    *,
    chat_id: int = 123456789,
    username: str | None = "tester",
    message_id: int = 1,
    from_id: int = 987654321,
) -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "message_id": message_id,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": from_id, "is_bot": False, "username": username},
            "text": text,
        },
    }


def make_start_update(
    token: str,
    *,
    chat_id: int = 123456789,
    username: str | None = "tester",
) -> dict[str, Any]:
    return make_message_update(f"/start {token}", chat_id=chat_id, username=username)


def make_callback_update(
    data: str,
    *,
    chat_id: int = 123456789,
    callback_query_id: str = "cq1",
) -> dict[str, Any]:
    return {
        "update_id": 2,
        "callback_query": {
            "id": callback_query_id,
            "data": data,
            "message": {"message_id": 10, "chat": {"id": chat_id, "type": "private"}},
            "from": {"id": 987654321, "is_bot": False},
        },
    }