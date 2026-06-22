from __future__ import annotations

from uuid import uuid4

import pytest

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.interview_prep_session_repository import InterviewPrepSessionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"

API_PREFIX = "/api/v1"


def _assert_keys(payload: dict, expected_keys: set[str]) -> None:
    assert set(payload) == expected_keys


async def _seed_interview_prep_contract_session(db_session, test_user):
    vacancy_repo = VacancyRepository()
    application_repo = ApplicationRecordRepository()
    analysis_repo = VacancyAnalysisRepository()
    session_repo = InterviewPrepSessionRepository()

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
            "Must have: Python, FastAPI, Kubernetes, PostgreSQL."
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
        ],
        nice_to_have_json=[],
        keywords_json=["Python", "FastAPI", "Kubernetes"],
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

    prep_session = await session_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        application_id=application.id,
        prep_status="draft",
        readiness_score=58,
        competency_map_json={
            "required_skills": [
                {"key": "python", "label": "Python", "source": "must_have"},
                {"key": "kubernetes", "label": "Kubernetes", "source": "must_have"},
            ],
            "seniority_expectations": {"level": "senior"},
        },
        question_set_json=[
            {
                "question_id": "q-technical-python",
                "category": "technical",
                "prompt": "Tell us about your Python backend experience.",
                "answer_format": "bullet",
                "competency_key": "python",
                "competency_name": "Python",
                "source_type": "vacancy_requirement",
                "source_requirement": "Python",
                "source_achievement_id": "a-python",
                "fact_status": "confirmed",
                "requires_careful_answer": False,
                "recommended_evidence_ids": ["a-python"],
                "recommended_evidence": [
                    {
                        "achievement_id": "a-python",
                        "title": "Built Python and FastAPI backend with PostgreSQL",
                        "score": 0.99,
                        "reason": "keyword overlap",
                        "source_type": "resume_structured",
                        "fact_status": "confirmed",
                        "skills": ["Python", "FastAPI"],
                        "match_confidence": "high",
                        "match_type": "exact_requirement",
                    }
                ],
                "suggested_answer": {
                    "format": "STAR_plus_tradeoffs",
                    "situation": "Built and supported backend services.",
                    "task": "Keep Python services reliable and fast.",
                    "action": "Refactored endpoints and improved deployment flow.",
                    "result": "Reduced release friction.",
                    "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
                    "tradeoffs": ["Need to confirm ownership details."],
                    "talking_points": ["Highlight backend delivery and collaboration."],
                    "source_evidence_id": "a-python",
                    "source_title": "Built Python and FastAPI backend with PostgreSQL",
                    "fact_status": "confirmed",
                    "grounding_status": "grounded",
                    "requires_human_review": True,
                    "draft_text": "Draft answer text",
                },
                "provenance": {
                    "source_type": "vacancy_requirement",
                    "source_requirement": "Python",
                    "source_achievement_id": "a-python",
                    "recommended_evidence_ids": ["a-python"],
                    "fact_status": "confirmed",
                    "requires_human_review": True,
                    "requires_careful_answer": False,
                },
            },
            {
                "question_id": "q-gap-kubernetes",
                "category": "gap-risk",
                "prompt": "How would you close the Kubernetes gap?",
                "answer_format": "narrative",
                "competency_key": "kubernetes",
                "competency_name": "Kubernetes",
                "source_type": "gap",
                "source_requirement": "Kubernetes",
                "source_achievement_id": None,
                "fact_status": "inferred_needs_review",
                "requires_careful_answer": True,
                "recommended_evidence_ids": [],
                "recommended_evidence": [],
                "suggested_answer": {
                    "format": "STAR_plus_tradeoffs",
                    "situation": "I do not have confirmed Kubernetes evidence yet.",
                    "task": "Be honest about the gap and show how I would close it.",
                    "action": "Describe a concrete learning plan and recent practice.",
                    "result": "Build confidence without inventing experience.",
                    "tech_stack": [],
                    "tradeoffs": ["Need to confirm ownership details."],
                    "talking_points": ["State the gap clearly."],
                    "source_evidence_id": None,
                    "source_title": None,
                    "fact_status": "inferred_needs_review",
                    "grounding_status": "insufficient_evidence",
                    "requires_human_review": True,
                    "draft_text": "Draft answer text",
                },
                "provenance": {
                    "source_type": "gap",
                    "source_requirement": "Kubernetes",
                    "source_achievement_id": None,
                    "recommended_evidence_ids": [],
                    "fact_status": "inferred_needs_review",
                    "requires_human_review": True,
                    "requires_careful_answer": True,
                },
            },
        ],
        evidence_links_json=[
            {
                "question_id": "q-technical-python",
                "question_category": "technical",
                "competency_key": "python",
                "achievement_id": "a-python",
                "achievement_title": "Built Python and FastAPI backend with PostgreSQL",
                "score": 0.99,
                "reason": "keyword overlap",
            }
        ],
        weak_areas_json=[
            {
                "code": "missing_confirmed_kubernetes",
                "message": "No confirmed Kubernetes evidence",
                "severity": "blocker",
                "category": "technical",
                "competency_key": "kubernetes",
                "evidence_count": 0,
            }
        ],
        readiness_json={
            "ready": False,
            "blockers": ["No confirmed Kubernetes evidence"],
            "warnings": ["No scale metrics"],
            "score": 58,
            "provenance": {
                "source": "achievement_mapping",
                "generation_mode": "deterministic_v1_review_ready",
                "application_id": str(application.id),
                "vacancy_id": str(vacancy.id),
                "analysis_id": str(uuid4()),
                "selected_achievement_ids": ["a-python"],
                "selected_evidence_ids": ["a-python"],
                "competency_sources": [
                    {
                        "competency_key": "python",
                        "source": "must_have",
                        "label": "Python",
                    }
                ],
                "question_generation_mode": "deterministic_v1",
                "question_source_counts": {
                    "vacancy_requirement": 1,
                    "gap": 1,
                },
                "confidence": 0.5,
                "confidence_level": "needs_review",
                "requires_human_review": True,
            },
        },
    )

    await db_session.commit()
    return prep_session


async def test_interview_prep_contract_snapshot(client, db_session, test_user):
    prep_session = await _seed_interview_prep_contract_session(db_session, test_user)

    response = await client.get(f"{API_PREFIX}/interview-prep/sessions/{prep_session.id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    _assert_keys(
        payload,
        {
            "id",
            "application_id",
            "vacancy_id",
            "prep_status",
            "readiness_score",
            "competency_map",
            "questions",
            "evidence_links",
            "weak_areas",
            "readiness",
            "provenance",
            "created_at",
            "updated_at",
        },
    )
    assert payload["id"] == str(prep_session.id)
    assert payload["prep_status"] == "draft"

    technical_question = next(
        item
        for item in payload["questions"]
        if item["category"] == "technical" and item["competency_key"] == "python"
    )
    _assert_keys(
        technical_question,
        {
            "question_id",
            "category",
            "prompt",
            "answer_format",
            "competency_key",
            "competency_name",
            "source_type",
            "source_requirement",
            "source_achievement_id",
            "fact_status",
            "requires_careful_answer",
            "recommended_evidence_ids",
            "recommended_evidence",
            "suggested_answer",
            "provenance",
        },
    )
    _assert_keys(
        technical_question["suggested_answer"],
        {
            "format",
            "situation",
            "task",
            "action",
            "result",
            "tech_stack",
            "tradeoffs",
            "talking_points",
            "source_evidence_id",
            "source_title",
            "fact_status",
            "grounding_status",
            "requires_human_review",
            "draft_text",
        },
    )
    assert technical_question["suggested_answer"]["requires_human_review"] is True

    gap_question = next(item for item in payload["questions"] if item["category"] == "gap-risk")
    _assert_keys(
        gap_question,
        {
            "question_id",
            "category",
            "prompt",
            "answer_format",
            "competency_key",
            "competency_name",
            "source_type",
            "source_requirement",
            "source_achievement_id",
            "fact_status",
            "requires_careful_answer",
            "recommended_evidence_ids",
            "recommended_evidence",
            "suggested_answer",
            "provenance",
        },
    )
    _assert_keys(
        gap_question["suggested_answer"],
        {
            "format",
            "situation",
            "task",
            "action",
            "result",
            "tech_stack",
            "tradeoffs",
            "talking_points",
            "source_evidence_id",
            "source_title",
            "fact_status",
            "grounding_status",
            "requires_human_review",
            "draft_text",
        },
    )
    assert gap_question["suggested_answer"]["requires_human_review"] is True
    assert gap_question["recommended_evidence"] == []
    assert gap_question["provenance"]["requires_human_review"] is True
