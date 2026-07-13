from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateAchievement, CandidateExperience, User
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _seed(client, db_session: AsyncSession, test_user: User) -> dict:
    profile_repo = CandidateProfileRepository()
    vacancy_repo = VacancyRepository()
    analysis_repo = VacancyAnalysisRepository()
    evidence_repo = EvidenceSnippetRepository()

    profile = await profile_repo.create_empty(db_session, user_id=test_user.id)
    profile.full_name = "Test Candidate"
    profile.headline = "Backend Engineer"
    profile.location = "Remote"
    profile.summary = "I keep stakeholders aligned and coordinate delivery."
    profile.target_roles_json = ["Backend Engineer"]

    experience = CandidateExperience(
        profile_id=profile.id,
        company="Acme",
        role="Backend Engineer",
        description_raw="Coordinated stakeholder updates and mentoring.",
        order_index=0,
    )
    db_session.add(experience)
    await db_session.flush()

    achievement = CandidateAchievement(
        profile_id=profile.id,
        experience_id=experience.id,
        title="Python delivery leadership",
        situation="The team needed a backend service shipped.",
        task="Deliver the service and coordinate stakeholders.",
        action="I led the Python implementation and weekly updates.",
        result="The service shipped on time.",
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
            "Must have: Python leadership, Kubernetes."
        ),
        normalized_json={"requirements": ["Python leadership", "Kubernetes"]},
    )

    await analysis_repo.replace_for_vacancy(
        db_session,
        vacancy_id=vacancy.id,
        must_have_json=[
            {"text": "Python leadership"},
            {"text": "Kubernetes"},
        ],
        nice_to_have_json=[{"text": "Redis"}],
        keywords_json=["Python leadership", "Kubernetes", "Redis"],
        gaps_json=[],
        strengths_json=[],
        match_score=70,
        analysis_version="deterministic_v1",
    )

    await evidence_repo.upsert_many(
        db_session,
        user_id=test_user.id,
        snippets=[
            {
                "fingerprint": "python-leadership-case",
                "title": "Python delivery leadership",
                "snippet_text": "Led the Python service implementation and kept stakeholders informed.",
                "source_type": "achievement",
                "skills": ["Python"],
                "evidence_strength": "strong",
                "fact_status": "confirmed",
                "star_summary": {
                    "situation": "Backend service needed delivery",
                    "task": "Ship the service and coordinate",
                    "action": "Led the Python implementation",
                    "result": "Service shipped on time",
                },
            },
        ],
    )

    await db_session.commit()
    return {"vacancy_id": vacancy.id}


async def _seed_foreign_vacancy(db_session: AsyncSession) -> str:
    foreign_user = User(
        email=f"foreign-{uuid4().hex}@local.test",
        password_hash="x",
        auth_provider="test",
    )
    db_session.add(foreign_user)
    await db_session.flush()
    vacancy_repo = VacancyRepository()
    vacancy = await vacancy_repo.create(
        db_session,
        user_id=foreign_user.id,
        source="manual",
        source_url=None,
        external_id=None,
        title="Other role",
        company="OtherCo",
        location="Remote",
        description_raw="Must have: Python.",
        normalized_json={"requirements": ["Python"]},
    )
    await db_session.commit()
    return str(vacancy.id)


async def test_get_cases_returns_explainable_case_set(client, db_session, test_user) -> None:
    from app.domain.case_prep import STABLE_CASE_TYPES

    seeded = await _seed(client, db_session, test_user)

    response = await client.get(f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["vacancy_id"] == str(seeded["vacancy_id"])
    assert body["cases"]
    for case in body["cases"]:
        assert case["case_type"] in STABLE_CASE_TYPES
        assert case["rubric"]
        assert case["suggested_approach"]
        assert case["framework"]
        assert case["time_guidance"]
        assert case["provenance"]["requires_human_review"] is True
    assert body["provenance"]["requires_human_review"] is True
    assert "vacancy_fit" in body["provenance"]["sources"]


async def test_get_cases_recommended_evidence_only_confirmed_or_user_provided(
    client, db_session, test_user
) -> None:
    seeded = await _seed(client, db_session, test_user)
    response = await client.get(f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}")
    assert response.status_code == 200, response.text
    body = response.json()

    has_any_evidence = False
    for case in body["cases"]:
        for ev in case["recommended_evidence"]:
            assert ev["fact_status"] in {"confirmed", "user_provided"}
            assert ev["match_type"] == "semantic"
            has_any_evidence = True
    # Хотя бы один кейс должен получить подтверждённую evidence (behavioral_case
    # якорится leadership-requirement с confirmed snippet).
    assert has_any_evidence


async def test_get_cases_has_no_fabricated_specifics(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    response = await client.get(f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    # title/prompt не должны содержать названия-заглушки компаний или суффиксы.
    import re

    suffix_re = re.compile(r"\b(inc|ltd|ооо|зао|пао)\b", re.IGNORECASE)
    for case in body["cases"]:
        text = f"{case['title']} {case['prompt']}".casefold()
        assert "acme" not in text
        assert "globex" not in text
        assert "contoso" not in text
        assert "testco" not in text
        assert not suffix_re.search(text)


async def test_get_cases_404_for_foreign_vacancy(client, db_session, test_user) -> None:
    await _seed(client, db_session, test_user)  # noqa: нужен лишь профиль текущего user
    foreign_id = await _seed_foreign_vacancy(db_session)

    response = await client.get(f"{API_PREFIX}/interview-prep/cases/{foreign_id}")
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "vacancy not found"


async def test_get_cases_404_for_random_uuid(client, db_session, test_user) -> None:
    await _seed(client, db_session, test_user)
    response = await client.get(f"{API_PREFIX}/interview-prep/cases/{uuid4()}")
    assert response.status_code == 404