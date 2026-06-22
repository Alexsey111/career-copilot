from __future__ import annotations

from uuid import uuid4

import pytest

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.interview_prep_session_repository import InterviewPrepSessionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


def _assert_keys(payload: dict, expected_keys: set[str]) -> None:
    assert set(payload) == expected_keys


async def _seed_review_summary_document(db_session, test_user):
    repo = DocumentVersionRepository()
    achievement_id = str(uuid4())
    analysis_id = str(uuid4())

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
            "based_on_analysis_id": analysis_id,
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
                "analysis_id": analysis_id,
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
        "provenance": {
            "source": "extracted",
            "generation_mode": "deterministic_v1_review_ready",
            "analysis_id": analysis_id,
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
                    }
                ],
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


async def _seed_health_diagnostics_data(db_session, test_user):
    vacancy_repo = VacancyRepository()
    application_repo = ApplicationRecordRepository()
    document_repo = DocumentVersionRepository()
    interview_repo = InterviewPrepSessionRepository()

    vacancy = await vacancy_repo.create(
        db_session,
        user_id=test_user.id,
        source="manual",
        source_url=None,
        external_id=None,
        title="Senior Backend Engineer",
        company="Acme",
        location="Remote",
        description_raw="Python, FastAPI, PostgreSQL.",
        normalized_json={"requirements": ["Python", "FastAPI", "PostgreSQL"]},
    )

    resume_document = await document_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        derived_from_id=None,
        analysis_id=None,
        document_kind="resume",
        version_label="resume_health_check",
        review_status="approved",
        is_active=True,
        content_json={"meta": {}, "sections": {}},
        rendered_text="Ready resume",
    )
    cover_letter_document = await document_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        derived_from_id=None,
        analysis_id=None,
        document_kind="cover_letter",
        version_label="cover_letter_health_check",
        review_status="approved",
        is_active=True,
        content_json={"meta": {}, "sections": {}},
        rendered_text="Ready cover letter",
    )

    application = await application_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        resume_document_id=resume_document.id,
        cover_letter_document_id=cover_letter_document.id,
        status="applied",
        source="manual",
        notes="Seeded for system health diagnostics",
    )

    await interview_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        application_id=application.id,
        prep_status="draft",
        readiness_score=72,
        competency_map_json={"required_skills": [{"key": "python", "label": "Python"}]},
        question_set_json=[],
        evidence_links_json=[],
        weak_areas_json=[],
        readiness_json={"ready": False, "warnings": ["Needs review"], "blockers": []},
    )

    await db_session.commit()
    return vacancy, application, resume_document, cover_letter_document


async def test_review_summary_document_contract_snapshot(client, db_session, test_user):
    document = await _seed_review_summary_document(db_session, test_user)

    response = await client.get(f"{API_PREFIX}/review/summary/document/{document.id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    _assert_keys(
        payload,
        {
            "entity_type",
            "entity_id",
            "ready",
            "requires_human_review",
            "risk_level",
            "quality",
            "blockers",
            "warnings",
            "claims_requiring_confirmation",
            "gap_risk_items",
            "selected_evidence",
            "provenance_summary",
            "recommended_actions",
        },
    )
    assert payload["entity_type"] == "document"
    assert payload["entity_id"] == str(document.id)
    assert payload["ready"] is False
    assert payload["requires_human_review"] is True
    assert payload["risk_level"] == "high"

    _assert_keys(
        payload["provenance_summary"],
        {
            "source",
            "generation_mode",
            "analysis_id",
            "selected_achievement_ids",
            "selected_evidence_ids",
            "evidence_selection_reason",
            "confidence",
            "generation_prompt_version",
            "generated_at",
            "requires_human_review",
            "confidence_level",
        },
    )
    assert payload["provenance_summary"]["source"] == "extracted"
    assert payload["provenance_summary"]["confidence_level"] == "needs_review"
    assert payload["selected_evidence"]
    assert payload["selected_evidence"][0]["source_type"] == "achievement"
    assert payload["claims_requiring_confirmation"]
    assert payload["gap_risk_items"]
    assert payload["recommended_actions"]


async def test_document_readiness_contract_snapshot(client, db_session, test_user):
    document = await _seed_review_summary_document(db_session, test_user)

    response = await client.get(f"{API_PREFIX}/documents/{document.id}/readiness")
    assert response.status_code == 200, response.text
    payload = response.json()

    _assert_keys(payload, {"ready", "blockers", "warnings", "score"})
    assert payload["ready"] is False
    assert payload["blockers"]
    assert payload["warnings"] == []
    assert payload["score"] == pytest.approx(0.87)


async def test_interview_prep_session_contract_snapshot(client, db_session, test_user):
    prep_session = await _seed_interview_prep_session(db_session, test_user)

    response = await client.get(
        f"{API_PREFIX}/interview-prep/sessions/{prep_session.id}",
    )
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
    assert payload["readiness_score"] == 58

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
            "provenance",
        },
    )
    assert technical_question["source_type"] == "vacancy_requirement"
    assert technical_question["fact_status"] == "confirmed"
    assert technical_question["provenance"]["requires_human_review"] is True

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
            "provenance",
        },
    )
    assert gap_question["source_type"] == "gap"
    assert gap_question["fact_status"] == "inferred_needs_review"
    assert gap_question["requires_careful_answer"] is True

    _assert_keys(
        payload["readiness"],
        {"ready", "blockers", "warnings", "score", "provenance", "question_summary"},
    )
    assert payload["readiness"]["ready"] is False
    assert payload["readiness"]["provenance"]["confidence_level"] == "needs_review"

    _assert_keys(
        payload["provenance"],
        {
            "source",
            "generation_mode",
            "application_id",
            "vacancy_id",
            "analysis_id",
            "selected_achievement_ids",
            "selected_evidence_ids",
            "competency_sources",
            "question_generation_mode",
            "question_source_counts",
            "confidence",
            "confidence_level",
            "requires_human_review",
        },
    )
    assert payload["provenance"]["source"] == "achievement_mapping"
    assert payload["provenance"]["confidence_level"] == "needs_review"


async def test_interview_prep_readiness_contract_snapshot(client, db_session, test_user):
    prep_session = await _seed_interview_prep_session(db_session, test_user)

    response = await client.get(
        f"{API_PREFIX}/interview-prep/sessions/{prep_session.id}/readiness",
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    _assert_keys(
        payload,
        {"ready", "blockers", "warnings", "score", "provenance", "question_summary"},
    )
    assert payload["ready"] is False
    assert payload["blockers"] == ["No confirmed Kubernetes evidence"]
    assert payload["warnings"] == ["No scale metrics"]
    assert payload["provenance"]["source"] == "achievement_mapping"
    assert payload["provenance"]["confidence_level"] == "needs_review"


async def test_health_diagnostics_contract_snapshot(client, db_session, test_user):
    vacancy, application, resume_document, cover_letter_document = await _seed_health_diagnostics_data(
        db_session,
        test_user,
    )

    response = await client.get(f"{API_PREFIX}/health/diagnostics")
    assert response.status_code == 200, response.text
    payload = response.json()

    _assert_keys(
        payload,
        {
            "status",
            "backend_reachable",
            "db_reachable",
            "current_user_id",
            "counts",
            "current_active_application",
            "active_documents",
            "demo_state",
            "scenario_identifiers",
        },
    )
    assert payload["status"] == "ok"
    assert payload["backend_reachable"] is True
    assert payload["db_reachable"] is True
    assert payload["current_user_id"] == str(test_user.id)

    _assert_keys(
        payload["counts"],
        {"vacancies", "applications", "documents", "interview_sessions"},
    )
    assert all(isinstance(value, int) for value in payload["counts"].values())

    _assert_keys(
        payload["current_active_application"],
        {
            "id",
            "vacancy_id",
            "status",
            "source",
            "resume_document_id",
            "cover_letter_document_id",
            "created_at",
            "updated_at",
        },
    )
    assert payload["current_active_application"]["id"] == str(application.id)
    assert payload["current_active_application"]["vacancy_id"] == str(vacancy.id)
    assert payload["current_active_application"]["resume_document_id"] == str(resume_document.id)
    assert payload["current_active_application"]["cover_letter_document_id"] == str(
        cover_letter_document.id
    )

    _assert_keys(
        payload["active_documents"],
        {"resume", "cover_letter"},
    )
    _assert_keys(
        payload["active_documents"]["resume"],
        {
            "id",
            "vacancy_id",
            "document_kind",
            "version_label",
            "review_status",
            "is_active",
            "created_at",
            "updated_at",
        },
    )
    _assert_keys(
        payload["active_documents"]["cover_letter"],
        {
            "id",
            "vacancy_id",
            "document_kind",
            "version_label",
            "review_status",
            "is_active",
            "created_at",
            "updated_at",
        },
    )

    _assert_keys(
        payload["demo_state"],
        {
            "has_demo_data",
            "has_vacancies",
            "has_applications",
            "has_documents",
            "has_active_documents",
            "has_interview_sessions",
            "current_active_application_id",
            "current_active_vacancy_id",
        },
    )
    assert payload["demo_state"]["has_demo_data"] is True
    assert payload["demo_state"]["current_active_application_id"] == str(application.id)
    assert payload["demo_state"]["current_active_vacancy_id"] == str(vacancy.id)

    assert len(payload["scenario_identifiers"]) >= 4
    _assert_keys(
        payload["scenario_identifiers"][0],
        {"code", "label", "description"},
    )
    assert payload["scenario_identifiers"][0]["code"] == "scenario_a_ready_application"
