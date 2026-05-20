from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.vacancy_fit_service import VacancyFitService


class _VacancyRepo:
    def __init__(self, vacancy) -> None:
        self.vacancy = vacancy

    async def get_by_id(self, session, vacancy_id, *, user_id):  # noqa: D401
        return self.vacancy


class _AnalysisRepo:
    def __init__(self, analysis) -> None:
        self.analysis = analysis

    async def get_latest_for_vacancy(self, session, vacancy_id, *, user_id):  # noqa: D401
        return self.analysis


class _ProfileRepo:
    def __init__(self, profile) -> None:
        self.profile = profile

    async def get_with_related_by_user_id(self, session, user_id):  # noqa: D401
        return self.profile


class _EvidenceRepo:
    def __init__(self, snippets) -> None:
        self.snippets = snippets

    async def list_by_user_id(self, session, *, user_id, source_types=None):  # noqa: D401
        return self.snippets


@pytest.mark.asyncio
async def test_vacancy_fit_service_classifies_gap_severity_and_evidence_coverage() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        title="Senior Backend Engineer",
        company="Acme",
        location="Remote",
        description_raw=(
            "Must have: Kubernetes, Leadership, Stakeholder communication.\n"
            "Python is also required."
        ),
    )
    analysis = SimpleNamespace(
        id=uuid4(),
        analysis_version="deterministic_v1",
        must_have_json=[
            {"text": "Kubernetes"},
            {"text": "Leadership"},
            {"text": "Stakeholder communication"},
            {"text": "Python"},
        ],
        nice_to_have_json=[
            {"text": "Redis"},
        ],
        keywords_json=["Kubernetes", "Leadership", "Stakeholder communication", "Python", "Redis"],
    )
    profile = SimpleNamespace(
        full_name="Test Candidate",
        headline="Backend Engineer",
        location="Remote",
        summary="I build backend systems and work closely with stakeholders.",
        target_roles_json=["Backend Engineer"],
        experiences=[
            SimpleNamespace(
                company="Acme",
                role="Backend Engineer",
                description_raw="Led delivery, coordinated stakeholders, and shipped Python services.",
            )
        ],
        achievements=[
            SimpleNamespace(
                title="Stakeholder communication",
                situation="The team needed a clearer release plan.",
                task="Keep stakeholders aligned.",
                action="I ran weekly updates and collected feedback.",
                result="The release stayed on track.",
                metric_text=None,
                evidence_note=None,
            )
        ],
    )
    snippets = [
        SimpleNamespace(
            id=uuid4(),
            title="Stakeholder communication",
            snippet_text="Weekly updates for product and support stakeholders.",
            source_type="achievement",
            skills_json=["Stakeholder communication", "communication"],
            evidence_strength="strong",
            fact_status="confirmed",
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary_json={
                "situation": "Release coordination needed alignment",
                "task": "Keep stakeholders informed",
                "action": "Sent weekly updates",
                "result": "Release stayed on track",
            },
        ),
        SimpleNamespace(
            id=uuid4(),
            title="Leadership",
            snippet_text="Led backend delivery and mentored one engineer.",
            source_type="achievement",
            skills_json=["Leadership", "mentoring"],
            evidence_strength="medium",
            fact_status="confirmed",
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary_json={
                "situation": "Team needed delivery support",
                "task": "Coordinate work",
                "action": "Led the backend stream",
                "result": "Milestones were met",
            },
        ),
    ]

    service = VacancyFitService(
        vacancy_repository=_VacancyRepo(vacancy),
        vacancy_analysis_repository=_AnalysisRepo(analysis),
        candidate_profile_repository=_ProfileRepo(profile),
        evidence_snippet_repository=_EvidenceRepo(snippets),
    )

    fit = await service.build_vacancy_fit(
        None,
        vacancy_id=vacancy.id,
        user_id=uuid4(),
    )

    assert fit["vacancy_id"] == vacancy.id
    assert fit["analysis_id"] == analysis.id
    assert fit["gap_severity"] == "critical"
    assert fit["readiness_recommendation"] == "Large evidence gaps"
    assert 0 <= fit["overall_fit_score"] <= 100

    required = fit["evidence_coverage"]["required"]
    assert any("kubernetes" in str(item).casefold() for item in required)
    assert any("leadership" in str(item).casefold() for item in required)
    assert any("stakeholder" in str(item).casefold() for item in required)

    strong = fit["evidence_coverage"]["strong"]
    medium = fit["evidence_coverage"]["medium"]
    missing = fit["evidence_coverage"]["missing"]

    assert any("stakeholder" in str(item["requirement"]).casefold() for item in strong)
    assert any("leadership" in str(item["requirement"]).casefold() for item in medium)
    assert any("kubernetes" in str(item["requirement"]).casefold() for item in missing)

    stakeholder_item = next(
        item for item in strong if "stakeholder" in str(item["requirement"]).casefold()
    )
    assert stakeholder_item["supporting_evidence"]
    assert stakeholder_item["supporting_evidence"][0]["fact_status"] == "confirmed"
    assert stakeholder_item["supporting_evidence"][0]["evidence_strength"] == "strong"
