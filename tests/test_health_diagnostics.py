from __future__ import annotations

import pytest

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.interview_prep_session_repository import InterviewPrepSessionRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio


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

    application = await application_repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=vacancy.id,
        status="applied",
        source="manual",
        notes="Seeded for system health diagnostics",
    )

    await document_repo.create(
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
    await document_repo.create(
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
    return vacancy, application


async def test_health_diagnostics_returns_current_demo_snapshot(client, db_session, test_user):
    vacancy, application = await _seed_health_diagnostics_data(db_session, test_user)

    response = await client.get("/api/v1/health/diagnostics")

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["backend_reachable"] is True
    assert payload["db_reachable"] is True
    assert payload["counts"]["vacancies"] == 1
    assert payload["counts"]["applications"] == 1
    assert payload["counts"]["documents"] == 2
    assert payload["counts"]["interview_sessions"] == 1
    assert payload["demo_state"]["has_demo_data"] is True
    assert payload["demo_state"]["current_active_application_id"] == str(application.id)
    assert payload["demo_state"]["current_active_vacancy_id"] == str(vacancy.id)
    assert payload["current_active_application"]["id"] == str(application.id)
    assert payload["current_active_application"]["vacancy_id"] == str(vacancy.id)
    assert payload["active_documents"]["resume"]["document_kind"] == "resume"
    assert payload["active_documents"]["cover_letter"]["document_kind"] == "cover_letter"
    assert payload["scenario_identifiers"]
    assert payload["scenario_identifiers"][0]["code"] == "scenario_a_ready_application"
