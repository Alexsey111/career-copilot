from __future__ import annotations

from datetime import datetime, timezone

import pytest


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _prepare_profile(client) -> None:
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

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


async def _create_analyzed_vacancy(client, title: str) -> str:
    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": title,
            "company": "Test Company",
            "location": "Remote",
            "description_raw": (
                "Требования:\n"
                "- Python\n"
                "- FastAPI\n"
                "- PostgreSQL\n"
            ),
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy_id = vacancy_response.json()["vacancy_id"]

    analysis_response = await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze",
    )
    assert analysis_response.status_code == 200, analysis_response.text

    return vacancy_id


async def _generate_and_approve_resume(client, vacancy_id: str) -> str:
    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    resume_document_id = resume_response.json()["document_id"]

    approve_response = await client.patch(
        f"{API_PREFIX}/documents/{resume_document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved in analytics test",
            "set_active_when_approved": True,
        },
    )
    assert approve_response.status_code == 200, approve_response.text

    return resume_document_id


async def _mark_application_ready(client, application_id: str) -> None:
    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "Ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text


async def test_application_analytics_summary_api_returns_user_rollup(client) -> None:
    await _prepare_profile(client)

    draft_vacancy_id = await _create_analyzed_vacancy(client, "Backend Developer")
    draft_resume_document_id = await _generate_and_approve_resume(client, draft_vacancy_id)

    draft_create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": draft_vacancy_id,
            "resume_document_id": draft_resume_document_id,
            "notes": "draft application for analytics",
        },
    )
    assert draft_create_response.status_code == 200, draft_create_response.text

    applied_vacancy_id = await _create_analyzed_vacancy(client, "Platform Engineer")
    applied_resume_document_id = await _generate_and_approve_resume(client, applied_vacancy_id)

    applied_create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": applied_vacancy_id,
            "resume_document_id": applied_resume_document_id,
            "notes": "applied application for analytics",
        },
    )
    assert applied_create_response.status_code == 200, applied_create_response.text
    applied_application_id = applied_create_response.json()["id"]

    await _mark_application_ready(client, applied_application_id)

    submit_response = await client.post(
        f"{API_PREFIX}/applications/{applied_application_id}/submit",
        json={"source": "manual", "external_link": "https://example.com/apply/analytics"},
    )
    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["status"] == "applied"

    response = await client.get(f"{API_PREFIX}/applications/analytics/summary")
    assert response.status_code == 200, response.text

    payload = response.json()
    today = datetime.now(timezone.utc).date().isoformat()

    assert payload["total_applications"] == 2
    assert payload["count_by_status"]["draft"] == 1
    assert payload["count_by_status"]["applied"] == 1
    assert payload["created_per_day"][today] == 2
    assert payload["applied_per_day"][today] == 1
    assert payload["conversion_to_applied"] == 0.5
    assert payload["offers_count"] == 0
    assert payload["rejections_count"] == 0
    assert payload["average_time_to_apply_hours"] is not None
    assert payload["average_time_to_apply_hours"] >= 0
