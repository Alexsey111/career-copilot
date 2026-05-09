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


async def _generate_and_approve_document_pair(client, vacancy_id: str) -> tuple[str, str]:
    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    resume_document_id = resume_response.json()["document_id"]

    cover_letter_response = await client.post(
        f"{API_PREFIX}/documents/letters/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert cover_letter_response.status_code == 200, cover_letter_response.text
    cover_letter_document_id = cover_letter_response.json()["document_id"]

    for document_id in (resume_document_id, cover_letter_document_id):
        approve_response = await client.patch(
            f"{API_PREFIX}/documents/{document_id}/review",
            json={
                "review_status": "approved",
                "review_comment": "approved in application list test",
                "set_active_when_approved": True,
            },
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["is_active"] is True

    return resume_document_id, cover_letter_document_id


async def test_application_list_returns_dashboard_fields(client) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    resume_id, cover_letter_id = await _generate_and_approve_document_pair(
        client,
        vacancy_id,
    )

    create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_id,
            "cover_letter_document_id": cover_letter_id,
            "notes": "dashboard list test",
        },
    )
    assert create_response.status_code == 200, create_response.text
    application_id = create_response.json()["id"]

    list_response = await client.get(f"{API_PREFIX}/applications")
    assert list_response.status_code == 200, list_response.text

    items = list_response.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    item = next(app for app in items if app["id"] == application_id)

    assert item["vacancy_id"] == vacancy_id
    assert item["vacancy_title"] == "Backend Developer"
    assert item["vacancy_company"] == "Test Company"
    assert item["vacancy_location"] == "Remote"
    assert item["resume_document_id"] == resume_id
    assert item["cover_letter_document_id"] == cover_letter_id
    assert item["status"] == "draft"
    assert item["source"] == "manual"
    assert item["notes"] == "dashboard list test"
    assert item["created_at"] is not None
    assert item["updated_at"] is not None