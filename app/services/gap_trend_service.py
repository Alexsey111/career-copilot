from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.vacancy_repository import VacancyRepository
from app.services.vacancy_fit_service import VacancyFitService


class GapTrendService:
    """Deterministic aggregation of recurring vacancy gaps."""

    SEVERITY_ORDER = {"critical": 3, "important": 2, "minor": 1}

    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_fit_service: VacancyFitService | None = None,
    ) -> None:
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_fit_service = vacancy_fit_service or VacancyFitService()

    async def build_gap_trends(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        limit: int = 20,
    ) -> dict[str, Any]:
        vacancies = await self.vacancy_repository.list_by_user_id(session, user_id=user_id)

        gap_counter: Counter[str] = Counter()
        severity_by_gap: dict[str, str] = {}
        examples_by_gap: dict[str, set[str]] = defaultdict(set)
        sample_fits: list[dict[str, Any]] = []

        for vacancy in vacancies[:limit]:
            fit = await self.vacancy_fit_service.build_vacancy_fit(
                session,
                vacancy_id=vacancy.id,
                user_id=user_id,
            )
            sample_fits.append(
                {
                    "vacancy_id": fit.get("vacancy_id"),
                    "vacancy_title": vacancy.title,
                    "overall_fit_score": fit.get("overall_fit_score"),
                    "gap_severity": fit.get("gap_severity"),
                    "readiness_recommendation": fit.get("readiness_recommendation"),
                }
            )

            for item in (fit.get("evidence_coverage") or {}).get("missing") or []:
                requirement = str(item.get("requirement") or "").strip()
                if not requirement:
                    continue
                gap_counter[requirement] += 1
                examples_by_gap[requirement].add(str(vacancy.title or "Vacancy"))
                severity = str(item.get("severity") or "minor").strip().lower()
                current = severity_by_gap.get(requirement)
                if current is None or self.SEVERITY_ORDER.get(severity, 0) > self.SEVERITY_ORDER.get(current, 0):
                    severity_by_gap[requirement] = severity

        recurring_gaps = []
        for requirement, count in gap_counter.most_common():
            recurring_gaps.append(
                {
                    "keyword": requirement,
                    "count": count,
                    "severity": severity_by_gap.get(requirement, "minor"),
                    "example_vacancy_titles": sorted(list(examples_by_gap.get(requirement, set())))[:3],
                }
            )

        return {
            "top_recurring_gaps": recurring_gaps[:10],
            "vacancy_samples": sample_fits[:5],
        }
