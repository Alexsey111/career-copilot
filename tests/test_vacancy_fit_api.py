from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models import CandidateAchievement, CandidateExperience
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _seed_profile_vacancy_and_evidence(db_session, test_user) -> dict:
    profile_repo = CandidateProfileRepository()
    vacancy_repo = VacancyRepository()
    analysis_repo = VacancyAnalysisRepository()
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
        metric_text=None,
        evidence_note="Confirmed in review.",
        fact_status="confirmed",
        order_index=0,
    )
    db_session.add(achievement)

    vacancy = await vacancy_repo.create(
        db_session,
        user_id=test_user.id,
        source="manual",
        source_url=None,
        external_id=None,
        title="Senior Backend Engineer",
        company="Acme",
        location="Remote",
        description_raw=(
            "Must have: Kubernetes, Leadership, Stakeholder communication.\n"
            "Python is also required."
        ),
        normalized_json={"requirements": ["Kubernetes", "Leadership", "Stakeholder communication"]},
    )

    await analysis_repo.replace_for_vacancy(
        db_session,
        vacancy_id=vacancy.id,
        must_have_json=[
            {"text": "Kubernetes"},
            {"text": "Leadership"},
            {"text": "Stakeholder communication"},
            {"text": "Python"},
        ],
        nice_to_have_json=[
            {"text": "Redis"},
        ],
        keywords_json=[
            "Kubernetes",
            "Leadership",
            "Stakeholder communication",
            "Python",
            "Redis",
        ],
        gaps_json=[],
        strengths_json=[],
        match_score=74,
        analysis_version="deterministic_v1",
    )

    await evidence_repo.upsert_many(
        db_session,
        user_id=test_user.id,
        snippets=[
            {
                "fingerprint": "stakeholder-communication-fit",
                "title": "Stakeholder communication",
                "snippet_text": "Weekly updates for product and support stakeholders.",
                "source_type": "achievement",
                "skills": ["Stakeholder communication", "communication"],
                "evidence_strength": "strong",
                "fact_status": "confirmed",
                "star_summary": {
                    "situation": "Release coordination needed alignment",
                    "task": "Keep stakeholders informed",
                    "action": "Sent weekly updates",
                    "result": "Release stayed on track",
                },
            },
            {
                "fingerprint": "leadership-fit",
                "title": "Leadership",
                "snippet_text": "Led backend delivery and mentored one engineer.",
                "source_type": "achievement",
                "skills": ["Leadership", "mentoring"],
                "evidence_strength": "medium",
                "fact_status": "confirmed",
                "star_summary": {
                    "situation": "Team needed delivery support",
                    "task": "Coordinate work",
                    "action": "Led the backend stream",
                    "result": "Milestones were met",
                },
            },
        ],
    )

    await db_session.commit()
    return {"vacancy": vacancy, "profile": profile}


async def test_vacancy_fit_api_returns_explainable_breakdown(client, db_session, test_user) -> None:
    seeded = await _seed_profile_vacancy_and_evidence(db_session, test_user)

    response = await client.get(f"{API_PREFIX}/vacancies/{seeded['vacancy'].id}/fit")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["vacancy_id"] == str(seeded["vacancy"].id)
    assert payload["analysis_version"] == "deterministic_v1"
    assert payload["gap_severity"] == "critical"
    assert payload["readiness_recommendation"] == "Large evidence gaps"
    assert 0 <= payload["overall_fit_score"] <= 100

    coverage = payload["evidence_coverage"]
    assert any("kubernetes" in str(item).casefold() for item in coverage["required"])

    strong = coverage["strong"]
    medium = coverage["medium"]
    missing = coverage["missing"]

    assert any("stakeholder" in item["requirement"].casefold() for item in strong)
    assert any("leadership" in item["requirement"].casefold() for item in medium)
    assert any("kubernetes" in item["requirement"].casefold() for item in missing)

    stakeholder_item = next(
        item for item in strong if "stakeholder" in item["requirement"].casefold()
    )
    assert stakeholder_item["supporting_evidence"]
    assert stakeholder_item["supporting_evidence"][0]["fact_status"] == "confirmed"
    assert stakeholder_item["supporting_evidence"][0]["evidence_strength"] == "strong"

