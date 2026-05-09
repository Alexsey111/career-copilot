from __future__ import annotations

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


async def _create_analyzed_vacancy(client) -> str:
    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
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


async def _generate_and_approve_resume(
    client,
    vacancy_id: str,
) -> str:
    response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    assert response.status_code == 200, response.text

    document_id = response.json()["document_id"]

    approve_response = await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved in status history test",
            "set_active_when_approved": True,
        },
    )

    assert approve_response.status_code == 200, approve_response.text

    return document_id


async def _create_application(client) -> str:
    await _prepare_profile(client)

    vacancy_id = await _create_analyzed_vacancy(client)

    await _generate_and_approve_resume(client, vacancy_id)

    response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "notes": "initial application",
        },
    )

    assert response.status_code == 200, response.text

    return response.json()["id"]


async def test_application_creates_initial_status_history(client) -> None:
    application_id = await _create_application(client)

    response = await client.get(
        f"{API_PREFIX}/applications/{application_id}/timeline",
    )

    assert response.status_code == 200, response.text

    timeline = response.json()

    assert len(timeline) == 1

    item = timeline[0]

    assert item["previous_status"] is None
    assert item["new_status"] == "draft"
    assert item["notes"] == "initial application"
    assert item["changed_at"] is not None


async def test_application_status_history_tracks_transitions(client) -> None:
    application_id = await _create_application(client)

    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    submitted_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "applied",
            "notes": "submitted on hh",
        },
    )

    assert submitted_response.status_code == 200, submitted_response.text

    interview_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "interview",
            "notes": "interview scheduled",
        },
    )

    assert interview_response.status_code == 200, interview_response.text

    timeline_response = await client.get(
        f"{API_PREFIX}/applications/{application_id}/timeline",
    )

    assert timeline_response.status_code == 200, timeline_response.text

    timeline = timeline_response.json()

    assert len(timeline) == 4

    assert timeline[0]["previous_status"] is None
    assert timeline[0]["new_status"] == "draft"

    assert timeline[1]["previous_status"] == "draft"
    assert timeline[1]["new_status"] == "ready"
    assert timeline[1]["notes"] == "ready for submission"

    assert timeline[2]["previous_status"] == "ready"
    assert timeline[2]["new_status"] == "applied"
    assert timeline[2]["notes"] == "submitted on hh"

    assert timeline[3]["previous_status"] == "applied"
    assert timeline[3]["new_status"] == "interview"
    assert timeline[3]["notes"] == "interview scheduled"


async def test_application_applied_at_set_only_once(client) -> None:
    application_id = await _create_application(client)

    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    submitted_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "applied",
            "notes": "submitted first time",
        },
    )

    assert submitted_response.status_code == 200, submitted_response.text

    first_applied_at = submitted_response.json()["applied_at"]

    interview_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "interview",
            "notes": "moved to interview",
        },
    )

    assert interview_response.status_code == 200, interview_response.text

    assert interview_response.json()["applied_at"] == first_applied_at


async def test_application_same_status_update_creates_history_entry(client) -> None:
    application_id = await _create_application(client)

    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    submitted_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "applied",
            "notes": "initial submit",
        },
    )

    assert submitted_response.status_code == 200, submitted_response.text

    repeated_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "applied",
            "notes": "updated notes only",
        },
    )

    assert repeated_response.status_code == 200, repeated_response.text

    timeline_response = await client.get(
        f"{API_PREFIX}/applications/{application_id}/timeline",
    )

    assert timeline_response.status_code == 200, timeline_response.text

    timeline = timeline_response.json()

    assert len(timeline) == 4

    assert timeline[1]["previous_status"] == "draft"
    assert timeline[1]["new_status"] == "ready"
    assert timeline[1]["notes"] == "ready for submission"

    assert timeline[2]["previous_status"] == "ready"
    assert timeline[2]["new_status"] == "applied"
    assert timeline[2]["notes"] == "initial submit"

    assert timeline[3]["previous_status"] == "applied"
    assert timeline[3]["new_status"] == "applied"
    assert timeline[3]["notes"] == "updated notes only"