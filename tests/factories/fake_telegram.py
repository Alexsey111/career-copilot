# tests/factories/fake_telegram.py

"""FakeTelegramClient для тестов Telegram companion (Этап 5). Полностью mock —
без реального токена и сети (выбор пользователя). Реализует тот же интерфейс,
что ``app.services.telegram_client.TelegramClient``, и записывает все вызовы.
"""

from __future__ import annotations

from typing import Any

from app.services.telegram_client import TelegramAPIError


class FakeTelegramClient:
    def __init__(self) -> None:
        self.send_message_calls: list[tuple[str, str]] = []
        self.set_webhook_calls: list[dict[str, Any]] = []
        # Настраиваемая ошибка (для теста error-handling в dispatch/webhook).
        self.send_error: Exception | None = None

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        if self.send_error is not None:
            raise self.send_error
        self.send_message_calls.append((str(chat_id), text))
        return {"ok": True, "result": {"message_id": len(self.send_message_calls)}}

    async def set_webhook(
        self,
        url: str,
        *,
        secret_token: str | None = None,
    ) -> dict[str, Any]:
        self.set_webhook_calls.append({"url": url, "secret_token": secret_token})
        return {"ok": True}

    async def get_me(self) -> dict[str, Any]:
        return {"ok": True, "result": {"id": 1, "username": "career_copilot_bot"}}

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
    ) -> dict[str, Any]:
        return {"ok": True}


def telegram_api_error(status_code: int = 400, detail: str = "bad request") -> TelegramAPIError:
    return TelegramAPIError(status_code, detail)