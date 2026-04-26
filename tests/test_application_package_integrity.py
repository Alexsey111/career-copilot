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


async def _create_analyzed_vacancy(client, *, title: str = "Backend Developer") -> str:
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


async def _generate_document_pair(client, vacancy_id: str) -> tuple[str, str]:
    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    resume_document_id = resume_response.json()["document_id"]

    letter_response = await client.post(
        f"{API_PREFIX}/documents/letters/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert letter_response.status_code == 200, letter_response.text
    cover_letter_document_id = letter_response.json()["document_id"]

    return resume_document_id, cover_letter_document_id


async def _approve_document(client, document_id: str) -> None:
    response = await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved in integrity test",
            "set_active_when_approved": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True


async def test_application_rejects_explicit_resume_from_another_vacancy(client) -> None:
    await _prepare_profile(client)

    vacancy_a_id = await _create_analyzed_vacancy(client, title="Backend Developer A")
    vacancy_b_id = await _create_analyzed_vacancy(client, title="Backend Developer B")

    resume_a_id, _ = await _generate_document_pair(client, vacancy_a_id)
    await _approve_document(client, resume_a_id)

    response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_b_id,
            "resume_document_id": resume_a_id,
            "notes": "try wrong vacancy resume",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "resume document does not belong to this vacancy"


async def test_application_rejects_resume_document_with_wrong_kind(client) -> None:
    await _prepare_profile(client)

    vacancy_id = await _create_analyzed_vacancy(client)
    _, cover_letter_id = await _generate_document_pair(client, vacancy_id)
    await _approve_document(client, cover_letter_id)

    response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": cover_letter_id,
            "notes": "try cover letter as resume",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "document must be resume"


async def test_application_rejects_cover_letter_document_with_wrong_kind(client) -> None:
    await _prepare_profile(client)

    vacancy_id = await _create_analyzed_vacancy(client)
    resume_id, _ = await _generate_document_pair(client, vacancy_id)
    await _approve_document(client, resume_id)

    response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_id,
            "cover_letter_document_id": resume_id,
            "notes": "try resume as cover letter",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "document must be cover_letter"


async def test_application_rejects_explicit_unapproved_resume(client) -> None:
    await _prepare_profile(client)

    vacancy_id = await _create_analyzed_vacancy(client)
    resume_id, _ = await _generate_document_pair(client, vacancy_id)

    response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_id,
            "notes": "try draft resume",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "resume document must be approved before application"


async def test_application_accepts_explicit_approved_document_pair(client) -> None:
    await _prepare_profile(client)

    vacancy_id = await _create_analyzed_vacancy(client)
    resume_id, cover_letter_id = await _generate_document_pair(client, vacancy_id)
    await _approve_document(client, resume_id)
    await _approve_document(client, cover_letter_id)

    response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_id,
            "cover_letter_document_id": cover_letter_id,
            "notes": "explicit approved package",
        },
    )

    assert response.status_code == 200, response.text
    application = response.json()
    assert application["resume_document_id"] == resume_id
    assert application["cover_letter_document_id"] == cover_letter_id