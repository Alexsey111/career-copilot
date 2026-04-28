from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document


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


async def _generate_resume(client, vacancy_id: str) -> str:
    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    return resume_response.json()["document_id"]


async def _approve_document(client, document_id: str) -> None:
    approve_response = await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved for docx export test",
            "set_active_when_approved": True,
        },
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["is_active"] is True


async def test_document_docx_export_requires_approved_active_document(client) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    document_id = await _generate_resume(client, vacancy_id)

    response = await client.get(f"{API_PREFIX}/documents/{document_id}/export/docx")

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "document must be approved and active before export"


async def test_document_docx_export_returns_valid_docx_for_approved_document(client) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    document_id = await _generate_resume(client, vacancy_id)
    await _approve_document(client, document_id)

    response = await client.get(f"{API_PREFIX}/documents/{document_id}/export/docx")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in response.headers["content-disposition"]
    assert response.content.startswith(b"PK")

    exported_doc = Document(BytesIO(response.content))
    exported_text = "\n".join(
        paragraph.text
        for paragraph in exported_doc.paragraphs
        if paragraph.text.strip()
    )

    assert "Backend Developer" in exported_text
    assert "needs_confirmation" not in exported_text