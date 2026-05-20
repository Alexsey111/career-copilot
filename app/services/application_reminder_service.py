# app\services\application_reminder_service.py

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.application_reminders import ApplicationReminder
from app.repositories.application_record_repository import ApplicationRecordRepository


class ApplicationReminderService:
    def __init__(
        self,
        application_record_repository: ApplicationRecordRepository | None = None,
        *,
        draft_stale_days: int = 14,
        ready_not_submitted_days: int = 7,
        follow_up_missing_days: int = 14,
    ) -> None:
        self.application_record_repository = (
            application_record_repository or ApplicationRecordRepository()
        )
        self.draft_stale_days = draft_stale_days
        self.ready_not_submitted_days = ready_not_submitted_days
        self.follow_up_missing_days = follow_up_missing_days

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _days_since(now: datetime, event_at: datetime) -> int:
        delta = now - event_at
        return max(0, delta.days)

    async def get_reminders(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[ApplicationReminder]:
        applications = await self.application_record_repository.list_by_user_id(
            session,
            user_id,
        )
        now = datetime.now(timezone.utc)
        reminders: list[ApplicationReminder] = []

        for application in applications:
            created_at = self._ensure_utc(application.created_at)
            updated_at = self._ensure_utc(application.updated_at)
            applied_at = (
                self._ensure_utc(application.applied_at)
                if application.applied_at is not None
                else None
            )

            if (
                application.status == "draft"
                and self._days_since(now, created_at) >= self.draft_stale_days
            ):
                days_since_event = self._days_since(now, created_at)
                reminders.append(
                    ApplicationReminder(
                        application_id=application.id,
                        reminder_type="draft_stale",
                        title="Черновик без активности",
                        description=(
                            f"Отклик в черновике уже {days_since_event} дн. "
                            "и не был обновлён."
                        ),
                        days_since_event=days_since_event,
                        created_at=now,
                    )
                )
                continue

            if (
                application.status == "ready"
                and self._days_since(now, updated_at) >= self.ready_not_submitted_days
            ):
                days_since_event = self._days_since(now, updated_at)
                reminders.append(
                    ApplicationReminder(
                        application_id=application.id,
                        reminder_type="ready_not_submitted",
                        title="Готов к отправке, но не отправлен",
                        description=(
                            f"Отклик в статусе ready уже {days_since_event} дн. "
                            "и ждёт отправки."
                        ),
                        days_since_event=days_since_event,
                        created_at=now,
                    )
                )
                continue

            if (
                application.status == "applied"
                and applied_at is not None
                and self._days_since(now, applied_at) >= self.follow_up_missing_days
            ):
                days_since_event = self._days_since(now, applied_at)
                reminders.append(
                    ApplicationReminder(
                        application_id=application.id,
                        reminder_type="follow_up_missing",
                        title="Нет follow-up по отклику",
                        description=(
                            f"Отклик отправлен {days_since_event} дн. назад "
                            "и по нему нет следующего этапа."
                        ),
                        days_since_event=days_since_event,
                        created_at=now,
                    )
                )

        reminders.sort(key=lambda item: (item.days_since_event, item.reminder_type), reverse=True)
        return reminders
