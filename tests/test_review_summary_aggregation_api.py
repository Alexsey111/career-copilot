from __future__ import annotations

from uuid import uuid4

import pytest

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.interview_prep_session_repository import (
    InterviewPrepSessionRepository,
)
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _seed_review_document(db_session, test_user):
    repo = DocumentVersionRepository()
    achievement_id = str(uuid4())
    content_json = {
        "draft_mode": "deterministic_v1_review_ready",
        "sections": {
            "selected_achievements": [
                {
                    "id": achievement_id,
                    "title": "Built Python and FastAPI backend with PostgreSQL",
                    "reason": "keyword_overlap",
                    "fact_status": "confirmed",
                    "metric_text": "20% faster deployments",
                }
            ],
            "claims_needing_confirmation": [
                {
                    "text": "Led a production rollout",
                    "fact_status": "needs_confirmation",
                }
            ],
            "warnings": [
                {
                    "code": "missing_vacancy_keywords",
                    "message": "profile does not strongly support these vacancy keywords yet: Kubernetes",
                    "severity": "warning",
                }
            ],
            "matched_keywords": ["Python", "FastAPI"],
            "missing_keywords": ["Kubernetes"],
            "selection_rationale": [
                {
                    "item": "Python",
                    "type": "keyword",
                    "reason": "vacancy_overlap",
                }
            ],
        },
        "meta": {
            "source": "extracted",
            "based_on_analysis_id": str(uuid4()),
            "selected_achievement_ids": [achievement_id],
            "selected_evidence_ids": [achievement_id],
            "evidence_selection_reason": [
                {
                    "evidence_id": achievement_id,
                    "achievement_id": achievement_id,
                    "title": "Built Python and FastAPI backend with PostgreSQL",
                    "reason": "keyword_overlap",
                }
            ],
            "confidence": 0.87,
            "generation_prompt_version": "resume_v1",
            "generated_at": "2026-05-21T00:00:00Z",
            "provenance": {
                "source": "extracted",
                "generation_mode": "deterministic_v1_review_ready",
                "analysis_id": str(uuid4()),
                "selected_achievement_ids": [achievement_id],
                "selected_evidence_ids": [achievement_id],
                "evidence_selection_reason": [
                    {
                        "evidence_id": achievement_id,
                        "achievement_id": achievement_id,
                        "title": "Built Python and FastAPI backend with PostgreSQL",
                        "reason": "keyword_overlap",
                    }
                ],
                "confidence": 0.87,
                "generation_prompt_version": "resume_v1",
                "generated_at": "2026-05-21T00:00:00Z",
                "requires_human_review": True,
            },
        },
        "readiness_score": {"overall_score": 0.87, "ats_score": 0.82},
    }

    document = await repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=None,
        derived_from_id=None,
        analysis_id=None,
        document_kind="resume",
        version_label="resume_draft_v1",
        review_status="draft",
        is_active=False,
        content_json=content_json,
        rendered_text="Draft resume text",
    )
    await db_session.commit()
    return document


async def _seed_interview_prep_session(db_session, test_user):
    vacancy_repo = VacancyRepository()
    application_repo = ApplicationRecordRepository()
    session_repo = InterviewPrepSessionRepository()
    analysis_repo = VacancyAnalysisRepository()

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
            "Leadership and scale metrics matter."
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
        nice_to_have_json=[],
        keywords_json=["Python", "FastAPI", "Kubernetes", "PostgreSQL"],
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

    question_id = "q-technical-python"
    gap_question_id = "q-gap-kubernetes"
    achievement_id = str(uuid4())
    ready_provenance = {
        "source": "achievement_mapping",
        "generation_mode": "deterministic_v1_review_ready",
        "application_id": str(application.id),
        "vacancy_id": str(vacancy.id),
        "analysis_id": str(uuid4()),
        "selected_achievement_ids": [achievement_id],
        "selected_evidence_ids": [achievement_id],
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
        "requires_human_review": True,
    }

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
                "question_id": question_id,
                "category": "technical",
                "prompt": "Tell us about your Python backend experience.",
                "answer_format": "bullet",
                "competency_key": "python",
                "competency_name": "Python",
                "source_type": "vacancy_requirement",
                "source_requirement": "Python",
                "source_achievement_id": achievement_id,
                "fact_status": "confirmed",
                "requires_careful_answer": False,
                "recommended_evidence_ids": [achievement_id],
                "recommended_evidence": [
                    {
                        "achievement_id": achievement_id,
                        "title": "Built Python and FastAPI backend with PostgreSQL",
                        "score": 0.99,
                        "reason": "keyword overlap",
                    }
                ],
                "provenance": {
                    "source_type": "vacancy_requirement",
                    "source_requirement": "Python",
                    "source_achievement_id": achievement_id,
                    "recommended_evidence_ids": [achievement_id],
                    "fact_status": "confirmed",
                    "requires_human_review": True,
                    "requires_careful_answer": False,
                },
            },
            {
                "question_id": gap_question_id,
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
                "question_id": question_id,
                "question_category": "technical",
                "achievement_id": achievement_id,
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
            "provenance": ready_provenance,
        },
    )

    await db_session.commit()
    return prep_session


async def test_review_summary_document_payload_is_unified(client, db_session, test_user):
    document = await _seed_review_document(db_session, test_user)

    response = await client.get(f"{API_PREFIX}/review/summary/document/{document.id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["entity_type"] == "document"
    assert payload["entity_id"] == str(document.id)
    assert payload["ready"] is False
    assert payload["requires_human_review"] is True
    assert payload["risk_level"] == "high"
    assert payload["blockers"]
    assert payload["warnings"]
    assert payload["claims_requiring_confirmation"]
    assert payload["gap_risk_items"]
    assert payload["selected_evidence"]
    assert payload["selected_evidence"][0]["source_type"] == "achievement"
    assert payload["provenance_summary"]["source"] == "extracted"
    assert payload["provenance_summary"]["requires_human_review"] is True
    assert payload["provenance_summary"]["confidence_level"] == "high"
    action_codes = {item["code"] for item in payload["recommended_actions"]}
    assert "confirm_claim" in action_codes
    assert "review_warning" in action_codes
    assert "resolve_blocker" in action_codes


async def test_review_summary_interview_prep_payload_is_unified(client, db_session, test_user):
    prep_session = await _seed_interview_prep_session(db_session, test_user)

    response = await client.get(
        f"{API_PREFIX}/review/summary/interview_prep/{prep_session.id}",
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["entity_type"] == "interview_prep"
    assert payload["entity_id"] == str(prep_session.id)
    assert payload["ready"] is False
    assert payload["requires_human_review"] is True
    assert payload["risk_level"] == "high"
    assert payload["blockers"] == ["No confirmed Kubernetes evidence"]
    assert payload["warnings"] == ["No scale metrics"]
    assert payload["claims_requiring_confirmation"] == []
    assert payload["gap_risk_items"]
    assert any(item["source_type"] == "gap_question" for item in payload["gap_risk_items"])
    assert payload["selected_evidence"]
    assert payload["selected_evidence"][0]["question_id"]
    assert payload["provenance_summary"]["source"] == "achievement_mapping"
    assert payload["provenance_summary"]["requires_human_review"] is True
    assert payload["provenance_summary"]["confidence_level"] == "needs_review"
    action_codes = {item["code"] for item in payload["recommended_actions"]}
    assert "prepare_gap_response" in action_codes
    assert "review_low_confidence" in action_codes
    assert "review_warning" in action_codes
