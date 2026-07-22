# app/services/telegram_dispatch_service.py

"""Proactive Telegram-уведомления (Этап 5, ТЗ §3.6).

Celery beat (``app.tasks.notification_tasks.dispatch_telegram_alerts``, раз в
час) вызывает ``dispatch_pending_alerts``. Для каждого пользователя с
привязанным Telegram и per-user opt-in:

1. ``ApplicationReminderService.get_reminders`` — готовые напоминания
   (draft_stale / ready_not_submitted / follow_up_missing). **Новой бизнес-логики
   нет** — переиспользуем существующий сервис.
2. Дедуп через ``telegram_dispatch_log`` (``dispatch_key`` =
   ``{reminder_type}:{application_id}:{YYYY-MM-DD}`` → максимум 1 уведомление
   типа на application в день, UTC). ``exists`` — первый слой;
   ``UniqueConstraint`` — второй (гонка при двойном beat-запуске).
3. ``TelegramClient.send_message`` (httpx). Ошибка отправки логируется, батч
   не роняется, лог-запись НЕ создаётся (только при success).

Security/privacy: ``chat_id`` не пишется в логи (pseudonymous, ФЗ-152). Логируем
только user_id и агрегаты (dispatched/skipped/errors).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.telegram_dispatch_log_repository import TelegramDispatchLogRepository
from app.repositories.user_repository import UserRepository
from app.services.application_reminder_service import ApplicationReminderService
from app.services.telegram_client import TelegramClient, TelegramAPIError

logger = logging.getLogger(__name__)


def _date_bucket(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


class TelegramDispatchService:
    def __init__(
        self,
        *,
        user_repo: UserRepository | None = None,
        reminder_service: ApplicationReminderService | None = None,
        dispatch_log_repo: TelegramDispatchLogRepository | None = None,
        telegram_client: TelegramClient | None = None,
    ) -> None:
        self.user_repo = user_repo or UserRepository()
        self.reminder_service = reminder_service or ApplicationReminderService()
        self.dispatch_log_repo = dispatch_log_repo or TelegramDispatchLogRepository()
        self.telegram_client = telegram_client or TelegramClient()

    async def dispatch_pending_alerts(self, session: AsyncSession) -> dict:
        """Рассылает proactive напоминания всем подписчикам. Возвращает
        ``{subscribers, dispatched, skipped, errors}``. Ошибка одного
        пользователя/напоминания не роняет остальных."""
        date_bucket = _date_bucket(datetime.now(timezone.utc))
        subscribers = await self.user_repo.list_telegram_subscribers(session)

        dispatched = 0
        skipped = 0
        errors = 0

        for user in subscribers:
            try:
                reminders = await self.reminder_service.get_reminders(
                    session, user_id=user.id
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "telegram dispatch: reminders fetch failed",
                    extra={"user_id": str(user.id)},
                )
                errors += 1
                continue

            for reminder in reminders:
                dispatch_key = (
                    f"{reminder.reminder_type}:{reminder.application_id}:{date_bucket}"
                )
                if await self.dispatch_log_repo.exists(
                    session, user_id=user.id, dispatch_key=dispatch_key
                ):
                    skipped += 1
                    continue

                text = self._format_reminder(reminder)
                try:
                    await self.telegram_client.send_message(
                        user.telegram_chat_id, text  # type: ignore[arg-type]
                    )
                except TelegramAPIError as exc:
                    logger.warning(
                        "telegram dispatch send failed",
                        extra={"user_id": str(user.id), "status": exc.status_code},
                    )
                    errors += 1
                    continue
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "telegram dispatch unexpected error",
                        extra={"user_id": str(user.id)},
                    )
                    errors += 1
                    continue

                payload_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                created = await self.dispatch_log_repo.create(
                    session,
                    user_id=user.id,
                    dispatch_key=dispatch_key,
                    dispatch_type=reminder.reminder_type,
                    payload_hash=payload_hash,
                )
                if created is not None:
                    dispatched += 1
                else:
                    # Гонка: другая beat-итерация уже записала лог → дедуп.
                    skipped += 1

            await session.commit()

        result = {
            "subscribers": len(subscribers),
            "dispatched": dispatched,
            "skipped": skipped,
            "errors": errors,
        }
        logger.info("telegram dispatch done: %s", result)
        return result

    @staticmethod
    def _format_reminder(reminder) -> str:
        return (
            f"⏰ {reminder.title}\n\n"
            f"{reminder.description}\n\n"
            "Подробно — в web-приложении."
        )