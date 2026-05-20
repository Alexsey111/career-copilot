from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.career_insights_service import CareerInsightsService


class _AnalyticsService:
    async def get_summary(self, session, *, user_id):  # noqa: D401
        return {
            "count_by_status": {
                "draft": 1,
                "applied": 2,
                "interview": 1,
                "rejected": 1,
                "offer": 0,
                "withdrawn": 0,
            },
            "offers_count": 0,
        }


class _GapTrendService:
    async def build_gap_trends(self, session, *, user_id, limit=20):  # noqa: D401
        return {
            "top_recurring_gaps": [
                {
                    "keyword": "Kubernetes",
                    "count": 3,
                    "severity": "critical",
                    "example_vacancy_titles": ["Platform Engineer"],
                },
                {
                    "keyword": "Leadership at scale",
                    "count": 2,
                    "severity": "important",
                    "example_vacancy_titles": ["Senior Backend Engineer"],
                },
            ],
            "vacancy_samples": [],
        }


class _EvidenceCoverageService:
    async def build_coverage_trends(self, session, *, user_id):  # noqa: D401
        return {
            "most_reusable_evidence": [
                {
                    "evidence_id": uuid4(),
                    "title": "Stakeholder communication",
                    "evidence_strength": "strong",
                    "fact_status": "confirmed",
                    "usage_count": 4,
                    "used_in_documents_count": 2,
                    "used_in_interviews_count": 1,
                    "reason": "Strong confirmed evidence with a reusable track record.",
                }
            ],
            "unused_evidence": [
                {
                    "evidence_id": uuid4(),
                    "title": "System design example",
                    "evidence_strength": "medium",
                    "fact_status": "confirmed",
                    "usage_count": 0,
                    "used_in_documents_count": 0,
                    "used_in_interviews_count": 0,
                    "reason": "Unused evidence is available for reuse.",
                }
            ],
            "weak_evidence_clusters": [
                {
                    "skill": "Kubernetes",
                    "count": 2,
                    "example_evidence_titles": ["Platform story"],
                }
            ],
        }


class _EvidenceInsightsService:
    async def get_evidence_insights(self, session, *, user_id):  # noqa: D401
        return {
            "missing_metrics_count": 2,
            "weak_evidence_count": 1,
            "missing_star_fields_count": 1,
            "unused_evidence_count": 1,
            "overused_evidence_count": 0,
            "unverified_evidence_count": 0,
            "recommendations": [],
        }


class _VacancyRepo:
    async def list_by_user_id(self, session, *, user_id):  # noqa: D401
        return [
            SimpleNamespace(id=uuid4(), title="Platform Engineer"),
            SimpleNamespace(id=uuid4(), title="Senior Backend Engineer"),
        ]


class _ApplicationRepo:
    async def list_by_user_id(self, session, user_id):  # noqa: D401
        rejected = SimpleNamespace(
            status="rejected",
            outcome="rejected",
            status_history=[
                SimpleNamespace(previous_status="screening", new_status="rejected"),
                SimpleNamespace(previous_status="interview", new_status="rejected"),
            ],
        )
        applied = SimpleNamespace(status="applied", outcome=None, status_history=[])
        interview = SimpleNamespace(status="interview", outcome=None, status_history=[])
        return [rejected, applied, interview]


@pytest.mark.asyncio
async def test_career_insights_service_builds_deterministic_guidance() -> None:
    service = CareerInsightsService(
        application_analytics_service=_AnalyticsService(),
        gap_trend_service=_GapTrendService(),
        evidence_coverage_service=_EvidenceCoverageService(),
        evidence_insights_service=_EvidenceInsightsService(),
        vacancy_repo=_VacancyRepo(),
        application_repo=_ApplicationRepo(),
    )

    summary = await service.build_career_insights(None, user_id=uuid4())

    assert summary["repeated_gaps"][0]["keyword"] == "Kubernetes"
    assert summary["evidence_coverage_trends"]["most_reusable_evidence"]
    assert summary["application_patterns"]["applications_sent"] == 4
    assert summary["application_patterns"]["interviews_reached"] == 2
    assert summary["application_patterns"]["most_common_rejection_stage"] == "screening"

    rec_titles = {item["title"] for item in summary["strategic_recommendations"]}
    assert "Add stronger leadership evidence" in rec_titles
    assert "Create STAR examples for Kubernetes" in rec_titles
    assert "Strengthen quantified impact metrics" in rec_titles
