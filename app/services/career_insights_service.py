from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.application_analytics_service import ApplicationAnalyticsService
from app.services.evidence_coverage_service import EvidenceCoverageService
from app.services.evidence_insights_service import EvidenceInsightsService
from app.services.gap_trend_service import GapTrendService
from app.services.vacancy_fit_service import VacancyFitService


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
        analytics = await self.application_analytics_service.get_summary(
            session,
            user_id=user_id,
        )
        applications = await self.application_repo.list_by_user_id(session, user_id)
        evidence_trends = await self.evidence_coverage_service.build_coverage_trends(
            session,
            user_id=user_id,
        )
        gap_trends = await self.gap_trend_service.build_gap_trends(
            session,
            user_id=user_id,
        )
        evidence_insights = await self.evidence_insights_service.get_evidence_insights(
            session,
            user_id=user_id,
        )
        vacancies = await self.vacancy_repo.list_by_user_id(session, user_id=user_id)

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
                        "title": "Add stronger leadership evidence",
                        "message": f"Repeated gap: {keyword}. Add a stronger leadership STAR example that shows scope and coordination.",
                        "priority": "high",
                    }
                )
            if "kubernetes" in lower:
                recommendations.append(
                    {
                        "code": "create_kubernetes_star",
                        "title": "Create STAR examples for Kubernetes",
                        "message": "Kubernetes appears as a recurring gap. Build one precise STAR story that shows actual delivery or operations work.",
                        "priority": "high",
                    }
                )
            if "system design" in lower or "architecture" in lower:
                recommendations.append(
                    {
                        "code": "strengthen_system_design",
                        "title": "Strengthen system design evidence",
                        "message": "System design is recurring. Capture an example with tradeoffs, scale, and rationale.",
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
                        "title": "Strengthen quantified impact metrics",
                        "message": f"Evidence around {skill} looks weak or repeated. Add numbers, outcomes, or scale indicators to improve reuse.",
                        "priority": "medium",
                    }
                )

        unused_evidence = evidence_trends.get("unused_evidence") or []
        if unused_evidence:
            recommendations.append(
                {
                    "code": "reuse_unused_evidence",
                    "title": "Reuse unused evidence",
                    "message": "You have unused evidence that could support future resume or interview drafts.",
                    "priority": "low",
                }
            )

        if evidence_insights.get("missing_metrics_count", 0) > 0:
            recommendations.append(
                {
                    "code": "add_metrics",
                    "title": "Add quantified impact metrics",
                    "message": "Some evidence still lacks metrics. Quantified outcomes usually make fit and reuse stronger.",
                    "priority": "medium",
                }
            )

        if application_patterns.get("most_common_rejection_stage"):
            stage = str(application_patterns["most_common_rejection_stage"])
            recommendations.append(
                {
                    "code": "address_rejection_stage",
                    "title": "Focus on the common rejection stage",
                    "message": f"Most rejections are happening around {stage}. Review the matching evidence and gaps for that stage.",
                    "priority": "medium",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "code": "maintain_current_direction",
                    "title": "Keep building reusable evidence",
                    "message": "Current signals look stable. Keep collecting confirmed evidence and use it across future vacancies.",
                    "priority": "low",
                }
            )

        return recommendations[:8]
