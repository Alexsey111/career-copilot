from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models import CandidateAchievement, CandidateExperience
from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.application_status_history_repository import (
    ApplicationStatusHistoryRepository,
)
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _seed_career_strategy_data(db_session, test_user) -> None:
    profile_repo = CandidateProfileRepository()
    vacancy_repo = VacancyRepository()
    analysis_repo = VacancyAnalysisRepository()
    application_repo = ApplicationRecordRepository()
    history_repo = ApplicationStatusHistoryRepository()
    evidence_repo = EvidenceSnippetRepository()

    profile = await profile_repo.create_empty(db_session, user_id=test_user.id)
    profile.full_name = "Test Candidate"
    profile.headline = "Backend Engineer"
    profile.location = "Remote"
    profile.summary = "I build backend systems and keep stakeholders aligned."
    profile.target_roles_json = ["Backend Engineer"]

    experience = CandidateExperience(
        profile_id=profile.id,
        company="Acme",
        role="Backend Engineer",
        description_raw="Led backend delivery and coordinated stakeholder updates.",
        order_index=0,
    )
    db_session.add(experience)
    await db_session.flush()

    achievement = CandidateAchievement(
        profile_id=profile.id,
        experience_id=experience.id,
        title="Stakeholder communication",
        situation="The team needed a clearer release plan.",
        task="Keep stakeholders informed.",
        action="I ran weekly updates and collected feedback.",
        result="The release stayed on track.",
        metric_text="Reduced escalations by 30%",
        evidence_note="Confirmed in review.",
        fact_status="confirmed",
        order_index=0,
    )
    db_session.add(achievement)

    await evidence_repo.upsert_many(
        db_session,
        user_id=test_user.id,
        snippets=[
            {
                "fingerprint": "stakeholder-coverage",
                "title": "Stakeholder communication",
                "snippet_text": "Weekly updates for product and support stakeholders.",
                "source_type": "achievement",
                "skills": ["Stakeholder communication", "communication"],
                "evidence_strength": "strong",
                "fact_status": "confirmed",
                "usage_count": 4,
                "used_in_documents_count": 2,
                "used_in_interviews_count": 1,
                "star_summary": {
                    "situation": "Release coordination needed alignment",
                    "task": "Keep stakeholders informed",
                    "action": "Sent weekly updates",
                    "result": "Release stayed on track",
                },
            },
            {
                "fingerprint": "unused-system-design",
                "title": "System design sketch",
                "snippet_text": "Designed a backend service boundary.",
                "source_type": "achievement",
                "skills": ["System design"],
                "evidence_strength": "medium",
                "fact_status": "confirmed",
                "usage_count": 0,
                "used_in_documents_count": 0,
                "used_in_interviews_count": 0,
                "star_summary": {
                    "situation": "Service boundaries were unclear",
                    "task": "Define the design",
                    "action": "Documented architecture decisions",
                    "result": "Team aligned on the design",
                },
            },
        ],
    )

    vacancy_specs = [
        ("Senior Backend Engineer", "rejected"),
        ("Platform Engineer", "rejected"),
        ("Staff Backend Engineer", "interview"),
    ]

    for title, status in vacancy_specs:
        vacancy = await vacancy_repo.create(
            db_session,
            user_id=test_user.id,
            source="manual",
            source_url=None,
            external_id=None,
            title=title,
            company="Acme",
            location="Remote",
            description_raw=(
                "Must have: Kubernetes, Leadership at scale, Stakeholder communication.\n"
                "Python is also required."
            ),
            normalized_json={"requirements": ["Kubernetes", "Leadership at scale", "Stakeholder communication"]},
        )

        await analysis_repo.replace_for_vacancy(
            db_session,
            vacancy_id=vacancy.id,
            must_have_json=[
                {"text": "Kubernetes"},
                {"text": "Leadership at scale"},
                {"text": "Stakeholder communication"},
                {"text": "Python"},
            ],
            nice_to_have_json=[
                {"text": "Redis"},
            ],
            keywords_json=[
                "Kubernetes",
                "Leadership at scale",
                "Stakeholder communication",
                "Python",
                "Redis",
            ],
            gaps_json=[],
            strengths_json=[],
            match_score=70,
            analysis_version="deterministic_v1",
        )

        application = await application_repo.create(
            db_session,
            user_id=test_user.id,
            vacancy_id=vacancy.id,
            status=status,
            source="manual",
            notes=f"{status} test application",
            outcome="rejected" if status == "rejected" else None,
        )

        if status == "rejected":
            await history_repo.create(
                db_session,
                application_id=application.id,
                previous_status="screening",
                new_status="rejected",
                notes="Rejected at screening",
            )

    await db_session.commit()


async def test_career_insights_summary_api_returns_operational_guidance(
    client,
    db_session,
    test_user,
) -> None:
    await _seed_career_strategy_data(db_session, test_user)

    response = await client.get(f"{API_PREFIX}/career-insights/summary")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["repeated_gaps"]
    assert payload["application_patterns"]["applications_sent"] == 3
    assert payload["application_patterns"]["most_common_rejection_stage"] == "screening"
    assert payload["evidence_coverage_trends"]["most_reusable_evidence"]
    assert payload["strategic_recommendations"]
    assert any(
        item["title"] in {
            "Add stronger leadership evidence",
            "Create STAR examples for Kubernetes",
            "Strengthen quantified impact metrics",
        }
        for item in payload["strategic_recommendations"]
    )
