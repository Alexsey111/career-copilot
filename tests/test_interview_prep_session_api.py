from __future__ import annotations

import pytest

from app.models import SourceFile
from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _prepare_profile_with_confirmed_achievements(
    client,
    db_session,
    test_user,
    fake_storage,
) -> list[dict]:
    extraction_repo = FileExtractionRepository()
    source_file = SourceFile(
        user_id=test_user.id,
        file_kind="resume",
        storage_key="test/interview-prep-session-api/resume.pdf",
        original_name="resume.pdf",
        mime_type="application/pdf",
        size_bytes=16,
    )
    db_session.add(source_file)
    await db_session.commit()
    await db_session.refresh(source_file)

    fake_storage[source_file.storage_key] = b"%PDF-1.4 fake pdf"

    source_file_id = str(source_file.id)

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

    extraction = await extraction_repo.get_by_id(
        db_session,
        extraction_id,
        user_id=test_user.id,
    )
    assert extraction is not None, "Imported file extraction must be visible before structuring"
    assert str(extraction.source_file_id) == source_file_id

    structured_response = await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    assert structured_response.status_code == 200, structured_response.text

    achievements_response = await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )
    assert achievements_response.status_code == 200, achievements_response.text
    achievements = achievements_response.json()["achievements"]
    assert len(achievements) >= 2

    updates = [
        {
            "title": "Built Python and FastAPI backend with PostgreSQL",
            "situation": "We needed a backend for a new product workflow.",
            "task": "Deliver a stable API with clear endpoints.",
            "action": "I implemented the service with Python, FastAPI and PostgreSQL.",
            "result": "The backend was ready for integration and review.",
            "fact_status": "confirmed",
            "evidence_note": "Confirmed technical delivery in review.",
        },
        {
            "title": "Hardened API error handling and tests",
            "situation": "The API needed more reliable behavior before release.",
            "task": "Improve resilience and test coverage.",
            "action": "I added validation, error handling and automated tests.",
            "result": "The service became easier to maintain and safer to ship.",
            "fact_status": "confirmed",
            "evidence_note": "Confirmed quality and testing work in review.",
        },
    ]

    for achievement, update in zip(achievements[:2], updates, strict=True):
        review_response = await client.patch(
            f"{API_PREFIX}/profile/achievements/{achievement['id']}/review",
            json={
                "title": update["title"],
                "situation": update["situation"],
                "task": update["task"],
                "action": update["action"],
                "result": update["result"],
                "fact_status": update["fact_status"],
                "evidence_note": update["evidence_note"],
            },
        )
        assert review_response.status_code == 200, review_response.text

    return achievements[:2]


async def _seed_vacancy_and_application(client, db_session, test_user) -> dict:
    vacancy_repo = VacancyRepository()
    analysis_repo = VacancyAnalysisRepository()
    application_repo = ApplicationRecordRepository()

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
            "We need a Senior Backend Engineer.\n"
            "Must have: Python, FastAPI, Kubernetes, PostgreSQL.\n"
            "Leadership, ownership, and cross-functional collaboration matter.\n"
            "Scale metrics and production reliability are expected."
        ),
        normalized_json={"requirements": ["Python", "FastAPI", "Kubernetes", "PostgreSQL"]},
    )

    await analysis_repo.replace_for_vacancy(
        db_session,
        vacancy_id=vacancy.id,
        must_have_json=[
            {"text": "Python", "keyword": "python", "weight": 100},
            {"text": "FastAPI", "keyword": "fastapi", "weight": 95},
            {"text": "Kubernetes", "keyword": "kubernetes", "weight": 90},
            {"text": "PostgreSQL", "keyword": "postgresql", "weight": 90},
        ],
        nice_to_have_json=[
            {"text": "Redis", "keyword": "redis", "weight": 40},
        ],
        keywords_json=[
            "Python",
            "FastAPI",
            "Kubernetes",
            "PostgreSQL",
            "leadership",
            "scale",
            "metrics",
        ],
        gaps_json=[
            {
                "keyword": "Kubernetes",
                "scope": "must_have",
                "reason": "No confirmed Kubernetes evidence yet",
                "requirement_text": "Kubernetes",
                "weight": 90,
            }
        ],
        strengths_json=[
            {
                "keyword": "Python",
                "scope": "must_have",
                "requirement_text": "Python",
                "evidence": "Confirmed backend work",
                "weight": 90,
            }
        ],
        match_score=84,
        analysis_version="v-test",
    )

    application = await application_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        status="applied",
        source="manual",
        notes="Manually submitted for interview prep",
    )

    await db_session.commit()
    return {
        "vacancy": vacancy,
        "application": application,
    }


@pytest.mark.asyncio
async def test_create_interview_prep_session_builds_deterministic_snapshot(
    client,
    db_session,
    test_user,
    fake_storage,
):
    await _prepare_profile_with_confirmed_achievements(
        client,
        db_session,
        test_user,
        fake_storage,
    )
    seeded = await _seed_vacancy_and_application(client, db_session, test_user)

    create_response = await client.post(
        f"{API_PREFIX}/interview-prep/sessions",
        json={"application_id": str(seeded["application"].id)},
    )
    assert create_response.status_code == 200, create_response.text
    payload = create_response.json()

    assert payload["application_id"] == str(seeded["application"].id)
    assert payload["vacancy_id"] == str(seeded["vacancy"].id)
    assert payload["prep_status"] == "draft"
    assert payload["readiness_score"] < 100

    questions = payload["questions"]
    categories = {item["category"] for item in questions}
    assert {"technical", "behavioral", "leadership", "project_deep_dive", "gap-risk"}.issubset(
        categories
    )

    technical_python_question = next(
        item
        for item in questions
        if item["category"] == "technical" and item["competency_key"] == "python"
    )
    assert technical_python_question["recommended_evidence_ids"]
    recommended_evidence = technical_python_question["recommended_evidence"]
    assert recommended_evidence
    assert recommended_evidence[0]["score"] >= recommended_evidence[-1]["score"]
    assert recommended_evidence[0]["title"] == "Built Python and FastAPI backend with PostgreSQL"
    suggested_answer = technical_python_question["suggested_answer"]
    assert suggested_answer["format"] == "STAR_plus_tradeoffs"
    assert suggested_answer["situation"] == "We needed a backend for a new product workflow."
    assert "Python" in suggested_answer["tech_stack"]
    assert "FastAPI" in suggested_answer["tech_stack"]
    assert suggested_answer["grounding_status"] == "grounded"
    assert suggested_answer["source_title"] == "Built Python and FastAPI backend with PostgreSQL"
    assert technical_python_question["recommended_evidence"][0]["match_confidence"] == "high"
    assert technical_python_question["recommended_evidence"][0]["match_type"] == "exact_requirement"

    evidence_links = payload["evidence_links"]
    assert any(
        link["question_id"] == technical_python_question["question_id"]
        and "Python" in link["achievement_title"]
        for link in evidence_links
    )

    weak_messages = {item["message"] for item in payload["weak_areas"]}
    assert "No confirmed Kubernetes evidence" in weak_messages
    assert "No leadership examples" in weak_messages
    assert "No scale metrics" in weak_messages

    readiness = payload["readiness"]
    assert readiness["ready"] is False
    assert "No confirmed Kubernetes evidence" in readiness["blockers"]
    assert "No leadership examples" in readiness["blockers"]
    assert "No scale metrics" in readiness["warnings"]

    gap_question = next(item for item in questions if item["category"] == "gap-risk")
    assert gap_question["suggested_answer"]["format"] == "honest_gap_response"
    assert gap_question["suggested_answer"]["requires_human_review"] is True

    provenance = payload["provenance"]
    assert provenance["source"] == "achievement_mapping"
    assert provenance["generation_mode"] == "deterministic_v1_review_ready"
    assert provenance["application_id"] == str(seeded["application"].id)
    assert provenance["vacancy_id"] == str(seeded["vacancy"].id)
    assert provenance["requires_human_review"] is True
    assert provenance["selected_achievement_ids"]
    assert provenance["selected_evidence_ids"]
    assert provenance["question_generation_mode"] == "deterministic_v1"
    assert provenance["confidence_level"] == "needs_review"

    assert readiness["provenance"] == provenance

    get_response = await client.get(
        f"{API_PREFIX}/interview-prep/sessions/{payload['id']}",
    )
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["id"] == payload["id"]

    readiness_response = await client.get(
        f"{API_PREFIX}/interview-prep/sessions/{payload['id']}/readiness",
    )
    assert readiness_response.status_code == 200, readiness_response.text
    assert readiness_response.json()["ready"] is False

    list_response = await client.get(f"{API_PREFIX}/interview-prep/sessions")
    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()) == 1

    assert technical_python_question["source_type"] == "vacancy_requirement"
    assert technical_python_question["source_requirement"] == "Python"
    assert technical_python_question["fact_status"] == "confirmed"
    assert technical_python_question["provenance"]["requires_human_review"] is True
    assert technical_python_question["provenance"]["recommended_evidence_ids"]
    assert technical_python_question["provenance"]["fact_status"] == "confirmed"

    gap_question = next(item for item in questions if item["category"] == "gap-risk")
    assert gap_question["source_type"] == "gap"
    assert gap_question["fact_status"] == "inferred_needs_review"
    assert gap_question["requires_careful_answer"] is True
    assert gap_question["provenance"]["requires_careful_answer"] is True
    assert gap_question["provenance"]["fact_status"] == "inferred_needs_review"
