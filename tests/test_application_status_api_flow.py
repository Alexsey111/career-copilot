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
                "\n"
                "Будет плюсом:\n"
                "- Redis\n"
                "- Docker\n"
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
            "review_comment": "approved in status flow test",
            "set_active_when_approved": True,
        },
    )
    assert approve_response.status_code == 200, approve_response.text

    return resume_document_id


async def _create_application(client) -> str:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    await _generate_and_approve_resume(client, vacancy_id)

    application_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "notes": "initial draft",
        },
    )
    assert application_response.status_code == 200, application_response.text
    return application_response.json()["id"]


async def test_application_status_api_accepts_valid_flow(client) -> None:
    application_id = await _create_application(client)

    submitted_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "submitted",
            "notes": "Submitted manually on HH",
        },
    )
    assert submitted_response.status_code == 200, submitted_response.text
    assert submitted_response.json()["status"] == "submitted"
    assert submitted_response.json()["applied_at"] is not None

    interview_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "interview",
            "notes": "Interview scheduled",
        },
    )
    assert interview_response.status_code == 200, interview_response.text
    assert interview_response.json()["status"] == "interview"

    offer_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "offer",
            "notes": "Offer received",
        },
    )
    assert offer_response.status_code == 200, offer_response.text
    assert offer_response.json()["status"] == "offer"
    assert offer_response.json()["outcome"] == "offer"


async def test_application_status_api_rejects_invalid_draft_to_offer(client) -> None:
    application_id = await _create_application(client)

    response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "offer",
            "notes": "Invalid direct offer",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "invalid application status transition: draft -> offer"


async def test_application_status_api_rejects_final_to_submitted(client) -> None:
    application_id = await _create_application(client)

    submitted_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "submitted",
            "notes": "Submitted manually",
        },
    )
    assert submitted_response.status_code == 200, submitted_response.text

    rejected_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "rejected",
            "notes": "Rejected by company",
        },
    )
    assert rejected_response.status_code == 200, rejected_response.text
    assert rejected_response.json()["status"] == "rejected"
    assert rejected_response.json()["outcome"] == "rejected"

    invalid_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "submitted",
            "notes": "Try to reopen as submitted",
        },
    )

    assert invalid_response.status_code == 400, invalid_response.text
    assert invalid_response.json()["detail"] == (
        "invalid application status transition: rejected -> submitted"
    )