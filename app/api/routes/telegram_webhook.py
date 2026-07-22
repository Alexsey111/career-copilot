# app/api/routes/telegram_webhook.py

"""Telegram webhook endpoint (Этап 5, ТЗ §3.6).

Raw body, без auth, без api-prefix (Telegram шлёт на корневой путь
``/webhooks/telegram``). Секрет проверяется по заголовку
``X-Telegram-Bot-Api-Secret-Token`` ( задаётся через ``setWebhook
secret_token``). Без секрета в dev — пропускаем с warning; в prod — 403
(prod-гард в ``validate_runtime_safety`` требует секрет при
``TELEGRAM_DISPATCH_ENABLED``, но webhook дублирует проверку defensively).

Образец webhook-паттерна: ``app/api/routes/stripe_webhook.py``.
"""

from __future__ import annotations

import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_telegram_client
from app.core.config import get_settings
from app.db.session import get_db_session
from app.schemas.telegram import TelegramWebhookAck
from app.services.telegram_client import TelegramClient, TelegramAPIError
from app.services.telegram_companion_service import TelegramCompanionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telegram-webhook"])


@router.post("/webhooks/telegram", response_model=TelegramWebhookAck)
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    telegram_client: TelegramClient = Depends(get_telegram_client),
) -> TelegramWebhookAck:
    settings = get_settings()
    expected_secret = settings.telegram_webhook_secret
    if expected_secret:
        provided = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(provided, expected_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="invalid telegram webhook secret",
            )
    elif settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="telegram webhook secret not configured",
        )
    else:
        logger.warning("telegram webhook secret not set — dev mode")

    body = await request.body()
    try:
        update = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid telegram payload: {exc}",
        )
    if not isinstance(update, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid telegram payload: expected object",
        )

    service = TelegramCompanionService()
    try:
        result = await service.handle_webhook_update(session, update, request=request)
        if result is not None:
            chat_id, reply_text = result
            await telegram_client.send_message(chat_id, reply_text)
        await session.commit()
    except TelegramAPIError as exc:
        # Telegram-API сбой при отправке ответа — не роняем webhook (Telegram
        # ретраит иначе). Логируем, откатываем транзакцию.
        logger.warning("telegram webhook send_message failed: status=%s", exc.status_code)
        await session.rollback()
    except Exception:
        logger.exception("telegram webhook handling failed")
        await session.rollback()
        raise

    return TelegramWebhookAck(ok=True)