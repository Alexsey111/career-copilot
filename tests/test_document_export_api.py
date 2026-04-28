from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _create_resume_and_cover_letter(client) -> tuple[str, str]:
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python, FastAPI, Docker", "text/plain")},
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

    analysis_response = await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")
    assert analysis_response.status_code == 200, analysis_response.text

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

    return resume_document_id, cover_letter_document_id


async def test_document_export_requires_approved_active_document(client) -> None:
    resume_document_id, _ = await _create_resume_and_cover_letter(client)

    response = await client.get(f"{API_PREFIX}/documents/{resume_document_id}/export/txt")

    assert response.status_code == 409
    assert response.json()["detail"] == "document must be approved and active before export"


async def test_document_export_returns_txt_and_md_for_approved_document(client) -> None:
    resume_document_id, cover_letter_document_id = await _create_resume_and_cover_letter(client)

    approve_resume_response = await client.patch(
        f"{API_PREFIX}/documents/{resume_document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "Approved for export test.",
            "set_active_when_approved": True,
        },
    )
    assert approve_resume_response.status_code == 200, approve_resume_response.text

    approve_letter_response = await client.patch(
        f"{API_PREFIX}/documents/{cover_letter_document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "Approved for export test.",
            "set_active_when_approved": True,
        },
    )
    assert approve_letter_response.status_code == 200, approve_letter_response.text

    resume_txt_response = await client.get(
        f"{API_PREFIX}/documents/{resume_document_id}/export/txt"
    )
    assert resume_txt_response.status_code == 200, resume_txt_response.text
    assert "text/plain" in resume_txt_response.headers["content-type"]
    assert "attachment;" in resume_txt_response.headers["content-disposition"]
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in resume_txt_response.text
    assert "КРАТКОЕ РЕЗЮМЕ" in resume_txt_response.text
    assert "needs_confirmation" not in resume_txt_response.text

    resume_md_response = await client.get(
        f"{API_PREFIX}/documents/{resume_document_id}/export/md"
    )
    assert resume_md_response.status_code == 200, resume_md_response.text
    assert "text/markdown" in resume_md_response.headers["content-type"]
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in resume_md_response.text

    letter_txt_response = await client.get(
        f"{API_PREFIX}/documents/{cover_letter_document_id}/export/txt"
    )
    assert letter_txt_response.status_code == 200, letter_txt_response.text
    assert "Здравствуйте" in letter_txt_response.text
    assert "needs_confirmation" not in letter_txt_response.text


async def test_document_export_rejects_unknown_format(client) -> None:
    resume_document_id, _ = await _create_resume_and_cover_letter(client)

    response = await client.get(f"{API_PREFIX}/documents/{resume_document_id}/export/pdf")

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported export format; use txt, md or docx"