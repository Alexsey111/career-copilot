from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.application_analytics_service import ApplicationAnalyticsService
from app.services.evidence_coverage_service import EvidenceCoverageService
from app.services.evidence_insights_service import EvidenceInsightsService
from app.services.gap_trend_service import GapTrendService
from app.services.vacancy_fit_service import VacancyFitService


logger = logging.getLogger(__name__)


class CareerInsightsService:
    """Deterministic operational guidance for career direction."""

    def __init__(
        self,
        application_analytics_service: ApplicationAnalyticsService | None = None,
        gap_trend_service: GapTrendService | None = None,
        evidence_coverage_service: EvidenceCoverageService | None = None,
        evidence_insights_service: EvidenceInsightsService | None = None,
        vacancy_repo: VacancyRepository | None = None,
        application_repo: ApplicationRecordRepository | None = None,
        evidence_repo: EvidenceSnippetRepository | None = None,
        vacancy_fit_service: VacancyFitService | None = None,
    ) -> None:
        self.application_analytics_service = application_analytics_service or ApplicationAnalyticsService()
        self.gap_trend_service = gap_trend_service or GapTrendService()
        self.evidence_coverage_service = evidence_coverage_service or EvidenceCoverageService()
        self.evidence_insights_service = evidence_insights_service or EvidenceInsightsService()
        self.vacancy_repo = vacancy_repo or VacancyRepository()
        self.application_repo = application_repo or ApplicationRecordRepository()
        self.evidence_repo = evidence_repo or EvidenceSnippetRepository()
        self.vacancy_fit_service = vacancy_fit_service or VacancyFitService()

    async def build_career_insights(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        analytics = await self._safe_call(
            component="application_analytics",
            fallback=self._empty_analytics(),
            call=self.application_analytics_service.get_summary(
                session,
                user_id=user_id,
            ),
        )
        applications = await self._safe_call(
            component="applications",
            fallback=[],
            call=self.application_repo.list_by_user_id(session, user_id),
        )
        evidence_trends = await self._safe_call(
            component="evidence_coverage",
            fallback=self._empty_evidence_trends(),
            call=self.evidence_coverage_service.build_coverage_trends(
                session,
                user_id=user_id,
            ),
        )
        gap_trends = await self._safe_call(
            component="gap_trends",
            fallback=self._empty_gap_trends(),
            call=self.gap_trend_service.build_gap_trends(
                session,
                user_id=user_id,
            ),
        )
        evidence_insights = await self._safe_call(
            component="evidence_insights",
            fallback=self._empty_evidence_insights(),
            call=self.evidence_insights_service.get_evidence_insights(
                session,
                user_id=user_id,
            ),
        )
        vacancies = await self._safe_call(
            component="vacancies",
            fallback=[],
            call=self.vacancy_repo.list_by_user_id(session, user_id=user_id),
        )

        application_patterns = self._build_application_patterns(
            analytics=analytics,
            applications=applications,
        )

        strategic_recommendations = self._build_recommendations(
            gap_trends=gap_trends,
            evidence_trends=evidence_trends,
            evidence_insights=evidence_insights,
            application_patterns=application_patterns,
        )

        vacancy_samples = gap_trends.get("vacancy_samples") or []
        if not vacancy_samples and vacancies:
            vacancy_samples = [
                {
                    "vacancy_id": vacancy.id,
                    "vacancy_title": vacancy.title,
                    "overall_fit_score": None,
                    "gap_severity": None,
                    "readiness_recommendation": None,
                }
                for vacancy in vacancies[:3]
            ]

        return {
            "generated_at": datetime.now(timezone.utc),
            "repeated_gaps": gap_trends.get("top_recurring_gaps") or [],
            "evidence_coverage_trends": evidence_trends,
            "application_patterns": application_patterns,
            "strategic_recommendations": strategic_recommendations,
            "vacancy_intelligence_sample": vacancy_samples,
        }

    async def _safe_call(
        self,
        *,
        component: str,
        fallback: Any,
        call,
    ) -> Any:
        try:
            return await call
        except HTTPException as exc:
            logger.warning(
                "career_insights_component_unavailable",
                extra={
                    "component": component,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
            return fallback

    def _empty_analytics(self) -> dict[str, Any]:
        return {
            "count_by_status": {},
            "offers_count": 0,
        }

    def _empty_evidence_trends(self) -> dict[str, Any]:
        return {
            "most_reusable_evidence": [],
            "unused_evidence": [],
            "weak_evidence_clusters": [],
        }

    def _empty_gap_trends(self) -> dict[str, Any]:
        return {
            "top_recurring_gaps": [],
            "vacancy_samples": [],
        }

    def _empty_evidence_insights(self) -> dict[str, Any]:
        return {
            "missing_metrics_count": 0,
            "weak_evidence_count": 0,
            "missing_star_fields_count": 0,
            "unused_evidence_count": 0,
            "overused_evidence_count": 0,
            "unverified_evidence_count": 0,
            "recommendations": [],
        }

    def _build_application_patterns(
        self,
        *,
        analytics: dict[str, Any],
        applications: list[Any],
    ) -> dict[str, Any]:
        count_by_status = analytics.get("count_by_status") or {}
        applications_sent = sum(
            int(count_by_status.get(status, 0))
            for status in ("applied", "screening", "interview", "offer", "rejected", "withdrawn")
        )
        interviews_reached = sum(
            int(count_by_status.get(status, 0))
            for status in ("interview", "offer", "rejected", "withdrawn")
        )
        offers_count = int(analytics.get("offers_count") or 0)

        rejection_stages: Counter[str] = Counter()
        for application in applications:
            if str(getattr(application, "outcome", "") or "").lower() != "rejected" and str(
                getattr(application, "status", "") or ""
            ).lower() != "rejected":
                continue

            history = getattr(application, "status_history", []) or []
            stage = "rejected"
            for item in history:
                if str(getattr(item, "new_status", "") or "").lower() == "rejected":
                    stage = str(getattr(item, "previous_status", "") or "rejected").strip().lower() or "rejected"
                    break
            rejection_stages[stage] += 1

        most_common_rejection_stage = None
        most_common_rejection_stage_count = 0
        if rejection_stages:
            most_common_rejection_stage, most_common_rejection_stage_count = rejection_stages.most_common(1)[0]

        conversion_to_interview = (
            round(interviews_reached / applications_sent, 4) if applications_sent else 0.0
        )
        conversion_to_offer = round(offers_count / applications_sent, 4) if applications_sent else 0.0

        return {
            "applications_sent": applications_sent,
            "interviews_reached": interviews_reached,
            "offers_count": offers_count,
            "most_common_rejection_stage": most_common_rejection_stage,
            "most_common_rejection_stage_count": most_common_rejection_stage_count,
            "conversion_to_interview": conversion_to_interview,
            "conversion_to_offer": conversion_to_offer,
        }

    def _build_recommendations(
        self,
        *,
        gap_trends: dict[str, Any],
        evidence_trends: dict[str, Any],
        evidence_insights: dict[str, Any],
        application_patterns: dict[str, Any],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []

        recurring_gaps = gap_trends.get("top_recurring_gaps") or []
        for top_gap in recurring_gaps[:3]:
            keyword = str(top_gap.get("keyword") or "").strip()
            if not keyword:
                continue
            lower = keyword.casefold()
            if any(token in lower for token in ["lead", "leadership", "stakeholder", "manager"]):
                recommendations.append(
                    {
                        "code": "strengthen_leadership_evidence",
                        "title": "Добавьте более сильные примеры лидерства",
                        "message": (
                            f"Повторяющийся пробел: {keyword}. Добавьте показательный "
                            "STAR-пример о лидерстве с указанием масштаба и координации."
                        ),
                        "priority": "high",
                    }
                )
            if "kubernetes" in lower:
                recommendations.append(
                    {
                        "code": "create_kubernetes_star",
                        "title": "Создайте STAR-пример по Kubernetes",
                        "message": (
                            "Kubernetes встречается как повторяющийся пробел. "
                            "Подготовьте точный STAR-рассказ о реальной эксплуатации или доставке."
                        ),
                        "priority": "high",
                    }
                )
            if "system design" in lower or "architecture" in lower:
                recommendations.append(
                    {
                        "code": "strengthen_system_design_evidence",
                        "title": "Усильте доказательства по system design",
                        "message": (
                            "System design встречается повторно. Зафиксируйте пример "
                            "с описанием компромиссов, масштаба и обоснования решений."
                        ),
                        "priority": "medium",
                    }
                )

        weak_clusters = evidence_trends.get("weak_evidence_clusters") or []
        if weak_clusters:
            top_cluster = weak_clusters[0]
            skill = str(top_cluster.get("skill") or "").strip()
            if skill:
                recommendations.append(
                    {
                        "code": "improve_metrics",
                        "title": "Усильте метрики количественного эффекта",
                        "message": (
                            f"Доказательства по «{skill}» выглядят слабыми или повторяющимися. "
                            "Добавьте цифры, результаты и индикаторы масштаба, "
                            "чтобы повысить переиспользуемость."
                        ),
                        "priority": "medium",
                    }
                )

        unused_evidence = evidence_trends.get("unused_evidence") or []
        if unused_evidence:
            recommendations.append(
                {
                    "code": "reuse_unused_evidence",
                    "title": "Используйте неиспользованные доказательства",
                    "message": (
                        "У вас есть неиспользованные доказательства, которые пригодятся "
                        "в будущих версиях резюме или подготовке к интервью."
                    ),
                    "priority": "low",
                }
            )

        if evidence_insights.get("missing_metrics_count", 0) > 0:
            recommendations.append(
                {
                    "code": "add_metrics",
                    "title": "Добавьте метрики количественного эффекта",
                    "message": (
                        "В части доказательств всё ещё нет метрик. Количественные "
                        "результаты обычно усиливают оценку соответствия и переиспользуемость."
                    ),
                    "priority": "medium",
                }
            )

        if application_patterns.get("most_common_rejection_stage"):
            stage = str(application_patterns["most_common_rejection_stage"])
            recommendations.append(
                {
                    "code": "address_rejection_stage",
                    "title": "Сфокусируйтесь на частом этапе отказа",
                    "message": (
                        f"Большинство отказов приходится на этап «{stage}». "
                        "Пересмотрите доказательства и пробелы по этому этапу."
                    ),
                    "priority": "medium",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "code": "maintain_current_direction",
                    "title": "Продолжайте копить переиспользуемые доказательства",
                    "message": (
                        "Сигналы стабильны. Продолжайте собирать подтверждённые "
                        "доказательства и применять их в новых вакансиях."
                    ),
                    "priority": "low",
                }
            )

        return recommendations[:8]
