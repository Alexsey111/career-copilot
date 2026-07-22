# app/services/telegram_link_service.py

"""Привязка Telegram-identity (Этап 5, ТЗ §3.6 / §3.1).

Web-пользователь (аутентифицирован) генерирует HMAC-signed stateless
``link_token`` (как OAuth ``state``), получает deep link
``https://t.me/<bot>?start=<token>``. Открыв бота, шлёт ``/start <token>`` →
webhook verify'ит HMAC + exp → сохраняет ``telegram_chat_id`` (plain
pseudonymous lookup-key, как ``oauth_provider_id``) + audit.

Security:
- ``link_token`` — stateless HMAC (не хранится в БД); подпись = ``jwt_secret``.
- Токен не содержит chat_id → атакующий своим chat_id не привяжется к чужому
  user_id без валидного токена (валидный токен выдаёт только web-auth user).
- Повторный ``/start <token>`` (в пределах TTL) идемпотентен.
- Один Telegram-аккаунт (chat_id) не может управлять двумя career-copilot
  user'ами одновременно: перелинковка chat_id к другому user очищает старого
  user'а + audit ``telegram_link_reassign`` (без unique-constraint — пересоздание
  аккаунта валидно). Образец HMAC: ``app/services/oauth_service.py:240-281``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import log_auth_event

logger = logging.getLogger(__name__)

_LINK_TOKEN_PREFIX = "tg"


def _state_key() -> bytes:
    return get_settings().jwt_secret.encode("utf-8")


class TelegramLinkService:
    def __init__(self, *, user_repository: UserRepository | None = None) -> None:
        self.user_repo = user_repository or UserRepository()

    # --- link token (stateless HMAC) ---

    def generate_link_token(self, user_id: UUID) -> str:
        """``tg:{user_id_hex}:{timestamp}:{nonce}.{signature}``."""
        nonce = secrets.token_urlsafe(16)
        timestamp = str(int(time.time()))
        payload = f"{_LINK_TOKEN_PREFIX}:{user_id.hex}:{timestamp}:{nonce}"
        signature = hmac.new(
            _state_key(), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"{payload}.{signature}"

    def verify_link_token(self, token: str) -> UUID | None:
        """Возвращает user_id при валидной подписи и неистёкшем TTL, иначе None."""
        if not token:
            return None
        try:
            payload, signature = token.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.new(
            _state_key(), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        parts = payload.split(":")
        if len(parts) != 4:
            return None
        prefix, user_id_hex, timestamp_str, _nonce = parts
        if prefix != _LINK_TOKEN_PREFIX:
            return None
        try:
            user_id = UUID(hex=user_id_hex)
        except ValueError:
            return None
        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return None
        ttl_seconds = get_settings().telegram_link_token_ttl_minutes * 60
        if abs(time.time() - timestamp) > ttl_seconds:
            return None
        return user_id

    def build_deep_link(self, token: str) -> str:
        username = (get_settings().telegram_bot_username or "").lstrip("@")
        if not username:
            raise RuntimeError("TELEGRAM_BOT_USERNAME is not configured")
        return f"https://t.me/{username}?start={token}"

    # --- link / unlink ---

    async def link_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        chat_id: str,
        username: str | None = None,
        request: Request | None = None,
    ) -> User:
        """Привязывает chat_id к user_id. Если chat_id уже был у другого user —
        отвязывает старого (audit ``telegram_link_reassign``).

        Сериализация по chat_id через ``pg_advisory_xact_lock`` защищает гонку:
        два конкурентных ``/start`` с разными валидными токенами и одним chat_id
        не оставят двух user'ов с одинаковым ``telegram_chat_id`` (что ломало бы
        ``get_by_telegram_chat_id`` через ``MultipleResultsFound``).
        """
        chat_id_str = str(chat_id)
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:c))"), {"c": chat_id_str}
        )
        prev_user = await self.user_repo.get_by_telegram_chat_id(session, chat_id_str)
        if prev_user is not None and prev_user.id != user_id:
            prev_user.telegram_chat_id = None
            prev_user.telegram_username = None
            prev_user.telegram_linked_at = None
            prev_user.telegram_dispatch_enabled = False
            await session.flush()
            if request is not None:
                await log_auth_event(
                    session,
                    event_type="telegram_link_reassign",
                    request=request,
                    user_id=user_id,
                    meta={
                        "prev_user_id": str(prev_user.id),
                        "chat_id": str(chat_id),
                    },
                )

        user = await self.user_repo.get_by_id(session, user_id)
        if user is None:
            raise ValueError(f"user not found: {user_id}")
        now = datetime.now(timezone.utc)
        user.telegram_chat_id = str(chat_id)
        user.telegram_username = username
        user.telegram_linked_at = now
        await session.flush()

        if request is not None:
            await log_auth_event(
                session,
                event_type="telegram_link",
                request=request,
                user_id=user.id,
                email=user.email,
                meta={"chat_id": str(chat_id)},
            )
        # ФЗ-152: логи без chat_id (pseudonymous, но не пишем в app-логи) — только user_id.
        logger.info("telegram linked user_id=%s", user_id)
        return user

    async def unlink(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        request: Request | None = None,
    ) -> User | None:
        user = await self.user_repo.get_by_id(session, user_id)
        if user is None:
            return None
        user.telegram_chat_id = None
        user.telegram_username = None
        user.telegram_linked_at = None
        user.telegram_dispatch_enabled = False
        await session.flush()
        if request is not None:
            await log_auth_event(
                session,
                event_type="telegram_unlink",
                request=request,
                user_id=user.id,
                email=user.email,
            )
        return user