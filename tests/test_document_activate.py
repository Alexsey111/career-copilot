from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_activate_requires_approved_document(client):
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

    document_id = generate_response.json()["document_id"]

    activate_response = await client.post(
        f"{API_PREFIX}/documents/{document_id}/activate"
    )

    assert activate_response.status_code == 409
    assert (
        activate_response.json()["detail"]
        == "only approved documents can be activated"
    )


async def test_activate_sets_document_active(client):
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

    document_id = generate_response.json()["document_id"]

    review_response = await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    assert review_response.status_code == 200

    activate_response = await client.post(
        f"{API_PREFIX}/documents/{document_id}/activate"
    )

    assert activate_response.status_code == 200

    data = activate_response.json()

    assert data["document_id"] == document_id
    assert data["is_active"] is True
async def test_activate_deactivates_previous_active_document(client):
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

    # Generate resume_v1
    generate_v1_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_v1_id = generate_v1_response.json()["document_id"]

    # Approve resume_v1
    await client.patch(
        f"{API_PREFIX}/documents/{document_v1_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": True,
        },
    )

    # Verify resume_v1 is active
    get_v1_response = await client.get(
        f"{API_PREFIX}/documents/{document_v1_id}"
    )
    assert get_v1_response.json()["is_active"] is True

    # Generate resume_v2
    generate_v2_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_v2_id = generate_v2_response.json()["document_id"]

    # Approve resume_v2
    await client.patch(
        f"{API_PREFIX}/documents/{document_v2_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    # Activate resume_v2
    activate_v2_response = await client.post(
        f"{API_PREFIX}/documents/{document_v2_id}/activate"
    )

    assert activate_v2_response.status_code == 200

    # Verify resume_v1 is now inactive
    get_v1_response = await client.get(
        f"{API_PREFIX}/documents/{document_v1_id}"
    )
    assert get_v1_response.json()["is_active"] is False

    # Verify resume_v2 is now active
    get_v2_response = await client.get(
        f"{API_PREFIX}/documents/{document_v2_id}"
    )
    assert get_v2_response.json()["is_active"] is True
