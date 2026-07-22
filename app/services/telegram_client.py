# app/services/telegram_client.py

"""Telegram Bot API клиент (Этап 5, ТЗ §3.6).

httpx напрямую (без SDK). Секреты (``telegram_bot_token``) — только в
settings/env, НИКОГДА в БД. Кастомное ``TelegramAPIError`` для 4xx/5xx —
ловится в webhook/dispatch и логируется, не роняя запрос. Образец
httpx-клиента + error-mapping: ``app/services/hh_vacancy_import_service.py``.

DI-mockable: ``app.api.dependencies.get_telegram_client`` фабрика (как
``get_stripe_client``); тесты подменяют через ``app.dependency_overrides``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    """4xx/5xx ответ Telegram Bot API (НЕ сетевая ошибка — те логируются отдельно)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"telegram api error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class TelegramClient:
    BASE_URL_TEMPLATE = "https://api.telegram.org/bot{token}/"
    TIMEOUT = 20.0

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        token = self._settings.telegram_bot_token
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        self._base_url = self.BASE_URL_TEMPLATE.format(token=token)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        """POST ``sendMessage``. Возвращает ответ Telegram (dict).

        Сетевые ошибки (ConnectError/Timeout/RequestError) логируются как
        warning и роняют ``TelegramAPIError``-обёртку, чтобы caller не
        анализировал типы исключений httpx. 4xx/5xx → ``TelegramAPIError``.
        """
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self.TIMEOUT
            ) as client:
                response = await client.post("sendMessage", json=payload)
        except httpx.ConnectError as exc:
            logger.warning("telegram sendMessage connect error: %s", exc)
            raise TelegramAPIError(502, "telegram api unavailable (connect)") from exc
        except httpx.TimeoutException as exc:
            logger.warning("telegram sendMessage timeout: %s", exc)
            raise TelegramAPIError(504, "telegram api timeout") from exc
        except httpx.RequestError as exc:
            logger.warning("telegram sendMessage request error: %s", exc)
            raise TelegramAPIError(502, f"telegram api request failed: {exc.__class__.__name__}") from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            # ФЗ-152: логи без chat_id и без текста сообщения (ПДн) — только статус.
            logger.warning("telegram sendMessage non-ok: status=%s", response.status_code)
            raise TelegramAPIError(response.status_code, detail)

        try:
            return response.json()
        except ValueError as exc:
            raise TelegramAPIError(502, "telegram api returned invalid JSON") from exc

    async def set_webhook(
        self,
        url: str,
        *,
        secret_token: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self.TIMEOUT
        ) as client:
            response = await client.post("setWebhook", json=payload)
        if response.status_code >= 400:
            raise TelegramAPIError(response.status_code, response.text[:500])
        return response.json()

    async def get_me(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self.TIMEOUT
        ) as client:
            response = await client.post("getMe")
        if response.status_code >= 400:
            raise TelegramAPIError(response.status_code, response.text[:500])
        return response.json()

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self.TIMEOUT
        ) as client:
            response = await client.post("answerCallbackQuery", json=payload)
        if response.status_code >= 400:
            raise TelegramAPIError(response.status_code, response.text[:500])
        return response.json()