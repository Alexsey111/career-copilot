# app\services\application_analytics_service.py

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.application_record_repository import ApplicationRecordRepository


class ApplicationAnalyticsService:
    def __init__(
        self,
        application_record_repository: ApplicationRecordRepository | None = None,
    ) -> None:
        self.application_record_repository = (
            application_record_repository or ApplicationRecordRepository()
        )

    async def get_summary(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        applications = await self.application_record_repository.list_by_user_id(
            session,
            user_id,
        )

        total = len(applications)
        count_by_status = Counter(app.status for app in applications)

        created_per_day: dict[str, int] = defaultdict(int)
        applied_per_day: dict[str, int] = defaultdict(int)
        time_to_apply_hours: list[float] = []

        for application in applications:
            if application.created_at:
                created_per_day[application.created_at.date().isoformat()] += 1

            if application.applied_at:
                applied_per_day[application.applied_at.date().isoformat()] += 1

            if application.created_at and application.applied_at:
                delta = application.applied_at - application.created_at
                time_to_apply_hours.append(delta.total_seconds() / 3600)

        submitted_or_later_count = sum(
            count_by_status.get(status, 0)
            for status in (
                "applied",
                "screening",
                "interview",
                "offer",
                "rejected",
                "withdrawn",
            )
        )

        conversion_to_applied = round(submitted_or_later_count / total, 4) if total > 0 else 0.0

        average_time_to_apply_hours = (
            round(sum(time_to_apply_hours) / len(time_to_apply_hours), 2)
            if time_to_apply_hours
            else None
        )

        return {
            "total_applications": total,
            "count_by_status": dict(count_by_status),
            "created_per_day": dict(sorted(created_per_day.items())),
            "applied_per_day": dict(sorted(applied_per_day.items())),
            "conversion_to_applied": conversion_to_applied,
            "offers_count": count_by_status.get("offer", 0),
            "rejections_count": count_by_status.get("rejected", 0),
            "average_time_to_apply_hours": average_time_to_apply_hours,
        }
