from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_get_active_document_success(client):
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

    # Approve and activate resume_v1
    await client.patch(
        f"{API_PREFIX}/documents/{document_v1_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": True,
        },
    )

    # Generate resume_v2
    generate_v2_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_v2_id = generate_v2_response.json()["document_id"]

    # Approve resume_v2 but don't activate
    await client.patch(
        f"{API_PREFIX}/documents/{document_v2_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    # Get active document
    active_response = await client.get(
        f"{API_PREFIX}/documents/active",
        params={"document_kind": "resume", "vacancy_id": vacancy_id},
    )

    assert active_response.status_code == 200

    data = active_response.json()

    # Should return v1 (the active one)
    assert data["id"] == document_v1_id
    assert data["is_active"] is True
    assert data["document_kind"] == "resume"


async def test_get_active_document_after_activation_switch(client):
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

    # Approve and activate resume_v1
    await client.patch(
        f"{API_PREFIX}/documents/{document_v1_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": True,
        },
    )

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

    # Activate v2
    await client.post(
        f"{API_PREFIX}/documents/{document_v2_id}/activate"
    )

    # Get active document
    active_response = await client.get(
        f"{API_PREFIX}/documents/active",
        params={"document_kind": "resume", "vacancy_id": vacancy_id},
    )

    assert active_response.status_code == 200

    data = active_response.json()

    # Should return v2 (now the active one)
    assert data["id"] == document_v2_id
    assert data["is_active"] is True
    assert data["document_kind"] == "resume"


async def test_get_active_document_returns_404(client):
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

    # Try to get active document without creating any
    active_response = await client.get(
        f"{API_PREFIX}/documents/active",
        params={"document_kind": "resume", "vacancy_id": vacancy_id},
    )

    assert active_response.status_code == 404
    assert active_response.json()["detail"] == "active document not found"
