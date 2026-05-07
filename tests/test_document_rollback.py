from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_document_rollback_creates_new_active_version(client):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )

    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )

    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )

    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )

    vacancy_id = vacancy_response.json()["vacancy_id"]

    await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze"
    )

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    original_document_id = generate_response.json()["document_id"]

    approve_response = await client.patch(
        f"{API_PREFIX}/documents/{original_document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": True,
        },
    )

    assert approve_response.status_code == 200

    rollback_response = await client.post(
        f"{API_PREFIX}/documents/{original_document_id}/rollback"
    )

    assert rollback_response.status_code == 200

    rollback_data = rollback_response.json()

    assert rollback_data["document_id"] != original_document_id
    assert rollback_data["source_document_id"] == original_document_id
    assert rollback_data["is_active"] is True

    new_document_response = await client.get(
        f"{API_PREFIX}/documents/{rollback_data['document_id']}"
    )

    assert new_document_response.status_code == 200

    new_document_data = new_document_response.json()

    assert new_document_data["is_active"] is True
    assert new_document_data["review_status"] == "approved"