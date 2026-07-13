from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.case_prep import STABLE_CASE_TYPES, build_rubric
from app.domain.interview_rubric_scoring import _RUBRIC_TOKENS
from app.models import CandidateAchievement, CandidateExperience, User
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.interview_prep_answer_attempt_repository import (
    InterviewPrepAnswerAttemptRepository,
)
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
        description_raw="Must have: Python leadership, Kubernetes.",
        normalized_json={"requirements": ["Python leadership", "Kubernetes"]},
    )

    await analysis_repo.replace_for_vacancy(
        db_session,
        vacancy_id=vacancy.id,
        must_have_json=[{"text": "Python leadership"}, {"text": "Kubernetes"}],
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


async def _first_case(client, vacancy_id) -> dict:
    response = await client.get(f"{API_PREFIX}/interview-prep/cases/{vacancy_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cases"], "seed should yield at least one case"
    return body["cases"][0]


def _full_answer(case_type: str) -> str:
    tokens: list[str] = []
    for crit_tokens in _RUBRIC_TOKENS[case_type].values():
        tokens.extend(crit_tokens)
    return " ".join(tokens)


async def test_submit_answer_scores_per_criterion(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    case = await _first_case(client, seeded["vacancy_id"])

    response = await client.post(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers",
        json={
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "answer_text": _full_answer(case["case_type"]),
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["case_id"] == case["case_id"]
    assert body["case_type"] in STABLE_CASE_TYPES
    assert len(body["criterion_scores"]) == 5
    assert 0 <= body["overall_score"] <= 100
    assert body["grade"] in {"excellent", "good", "needs_work", "weak"}
    assert body["requires_human_review"] is True
    assert body["rubric_version"] == "deterministic_v1"
    assert body["attempt_id"]
    from datetime import datetime

    datetime.fromisoformat(body["created_at"])


async def test_submit_answer_case_type_in_stable_types(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    case = await _first_case(client, seeded["vacancy_id"])
    assert case["case_type"] in STABLE_CASE_TYPES


async def test_list_attempts_after_two_submits(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    case = await _first_case(client, seeded["vacancy_id"])
    url = f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers"

    for _ in range(2):
        r = await client.post(
            url,
            json={
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "answer_text": _full_answer(case["case_type"]),
            },
        )
        assert r.status_code == 201, r.text

    list_resp = await client.get(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/attempts",
        params={"case_id": case["case_id"]},
    )
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()
    assert len(items) == 2
    # ordered asc by created_at
    assert items[0]["created_at"] <= items[1]["created_at"]


async def test_progress_improving_after_weak_then_strong(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    case = await _first_case(client, seeded["vacancy_id"])
    url = f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers"

    weak = await client.post(
        url,
        json={
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "answer_text": "ok",
        },
    )
    assert weak.status_code == 201
    strong = await client.post(
        url,
        json={
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "answer_text": _full_answer(case["case_type"]),
        },
    )
    assert strong.status_code == 201
    assert weak.json()["overall_score"] < strong.json()["overall_score"]

    progress = await client.get(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/progress",
        params={"case_id": case["case_id"]},
    )
    assert progress.status_code == 200, progress.text
    body = progress.json()
    assert body["total_attempts"] == 2
    assert body["overall"]["first"] < body["overall"]["last"]
    assert body["overall"]["trend"] == "improving"


async def test_progress_empty_for_fresh_case_id(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    progress = await client.get(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/progress",
        params={"case_id": "ipc_fresh_no_attempts_yet"},
    )
    assert progress.status_code == 200, progress.text
    body = progress.json()
    assert body["total_attempts"] == 0
    assert body["reason"] == "no attempts yet"
    assert body["overall"] is None
    assert body["per_criterion"] == []


async def test_submit_answer_404_for_foreign_vacancy(client, db_session, test_user) -> None:
    await _seed(client, db_session, test_user)
    foreign_id = await _seed_foreign_vacancy(db_session)
    response = await client.post(
        f"{API_PREFIX}/interview-prep/cases/{foreign_id}/answers",
        json={"case_id": "ipc_x", "case_type": "system_design", "answer_text": "scalab throughput"},
    )
    assert response.status_code == 404


async def test_submit_answer_404_for_random_uuid(client, db_session, test_user) -> None:
    await _seed(client, db_session, test_user)
    response = await client.post(
        f"{API_PREFIX}/interview-prep/cases/{uuid4()}/answers",
        json={"case_id": "ipc_x", "case_type": "system_design", "answer_text": "scalab throughput"},
    )
    assert response.status_code == 404


async def test_submit_answer_400_invalid_case_type(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    response = await client.post(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers",
        json={"case_id": "ipc_x", "case_type": "bogus", "answer_text": "some answer"},
    )
    assert response.status_code == 400


async def test_submit_answer_422_empty_answer_text(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    response = await client.post(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers",
        json={"case_id": "ipc_x", "case_type": "system_design", "answer_text": ""},
    )
    assert response.status_code == 422


async def test_list_attempts_404_for_foreign_vacancy(client, db_session, test_user) -> None:
    await _seed(client, db_session, test_user)
    foreign_id = await _seed_foreign_vacancy(db_session)
    response = await client.get(
        f"{API_PREFIX}/interview-prep/cases/{foreign_id}/attempts",
        params={"case_id": "ipc_x"},
    )
    assert response.status_code == 404


async def test_progress_404_for_foreign_vacancy(client, db_session, test_user) -> None:
    await _seed(client, db_session, test_user)
    foreign_id = await _seed_foreign_vacancy(db_session)
    response = await client.get(
        f"{API_PREFIX}/interview-prep/cases/{foreign_id}/progress",
        params={"case_id": "ipc_x"},
    )
    assert response.status_code == 404


async def test_answer_text_encrypted_at_rest(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    case = await _first_case(client, seeded["vacancy_id"])
    marker = f"ivan-{uuid4().hex}@local.test"

    response = await client.post(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers",
        json={
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "answer_text": f"{marker} scalable throughput latency failure outage retry tradeoff",
        },
    )
    assert response.status_code == 201, response.text
    attempt_id = response.json()["attempt_id"]

    # Raw column — must NOT contain the plaintext marker (Fernet base64 at rest).
    raw_answer_text = await db_session.scalar(
        text("SELECT answer_text FROM interview_prep_answer_attempts WHERE id = :id"),
        {"id": attempt_id},
    )
    assert raw_answer_text is not None
    assert marker not in raw_answer_text
    assert "ivan" not in raw_answer_text

    # ORM read — decrypted, contains the marker.
    repo = InterviewPrepAnswerAttemptRepository()
    attempt = await repo.get_by_id(db_session, uuid4_from_str(attempt_id), user_id=test_user.id)
    assert attempt is not None
    assert marker in attempt.answer_text


async def test_progress_per_criterion_matches_build_rubric(client, db_session, test_user) -> None:
    seeded = await _seed(client, db_session, test_user)
    case = await _first_case(client, seeded["vacancy_id"])

    await client.post(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/answers",
        json={
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "answer_text": _full_answer(case["case_type"]),
        },
    )
    progress = await client.get(
        f"{API_PREFIX}/interview-prep/cases/{seeded['vacancy_id']}/progress",
        params={"case_id": case["case_id"]},
    )
    assert progress.status_code == 200, progress.text
    body = progress.json()
    expected = build_rubric(case["case_type"])
    actual = [p["criterion"] for p in body["per_criterion"]]
    assert actual == expected


def uuid4_from_str(value: str):
    from uuid import UUID

    return UUID(value)