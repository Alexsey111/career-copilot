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

        conversion_by_resume_version = self._compute_conversion_by_resume_version(applications)
        conversion_by_role = self._compute_conversion_by_role(applications)

        return {
            "total_applications": total,
            "count_by_status": dict(count_by_status),
            "created_per_day": dict(sorted(created_per_day.items())),
            "applied_per_day": dict(sorted(applied_per_day.items())),
            "conversion_to_applied": conversion_to_applied,
            "offers_count": count_by_status.get("offer", 0),
            "rejections_count": count_by_status.get("rejected", 0),
            "average_time_to_apply_hours": average_time_to_apply_hours,
            "conversion_by_resume_version": conversion_by_resume_version,
            "conversion_by_role": conversion_by_role,
        }

    def _compute_conversion_by_resume_version(
        self,
        applications: list,
    ) -> dict[str, dict[str, Any]]:
        version_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "interview": 0, "offer": 0})
        for app in applications:
            version_label = "unknown"
            if app.resume_document and getattr(app.resume_document, "version_label", None):
                version_label = app.resume_document.version_label
            version_stats[version_label]["total"] += 1
            if app.status == "interview":
                version_stats[version_label]["interview"] += 1
            if app.status == "offer":
                version_stats[version_label]["offer"] += 1

        result: dict[str, dict[str, Any]] = {}
        for version, stats in version_stats.items():
            total = stats["total"]
            result[version] = {
                "total": total,
                "interview_count": stats["interview"],
                "offer_count": stats["offer"],
                "interview_rate": round(stats["interview"] / total, 4) if total > 0 else 0.0,
                "offer_rate": round(stats["offer"] / total, 4) if total > 0 else 0.0,
            }
        return result

    def _compute_conversion_by_role(
        self,
        applications: list,
    ) -> dict[str, dict[str, Any]]:
        role_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "interview": 0, "offer": 0})
        for app in applications:
            role = "unknown"
            if app.vacancy and getattr(app.vacancy, "title", None):
                role = app.vacancy.title
            role_stats[role]["total"] += 1
            if app.status == "interview":
                role_stats[role]["interview"] += 1
            if app.status == "offer":
                role_stats[role]["offer"] += 1

        result: dict[str, dict[str, Any]] = {}
        for role, stats in role_stats.items():
            total = stats["total"]
            result[role] = {
                "total": total,
                "interview_count": stats["interview"],
                "offer_count": stats["offer"],
                "interview_rate": round(stats["interview"] / total, 4) if total > 0 else 0.0,
                "offer_rate": round(stats["offer"] / total, 4) if total > 0 else 0.0,
            }
        return result
