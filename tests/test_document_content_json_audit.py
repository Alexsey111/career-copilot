from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentVersion


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _get_document(
    db_session: AsyncSession,
    document_id: str,
) -> DocumentVersion:
    result = await db_session.execute(
        select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
    )
    document = result.scalar_one_or_none()
    assert document is not None
    return document


async def test_generated_documents_content_json_contains_review_audit_fields(
    client,
    db_session: AsyncSession,
) -> None:
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

    resume_document = await _get_document(db_session, resume_document_id)
    cover_letter_document = await _get_document(db_session, cover_letter_document_id)

    resume_content = resume_document.content_json
    resume_sections = resume_content["sections"]

    assert resume_content["document_kind"] == "resume"
    assert resume_content["draft_mode"] == "deterministic_v1_review_ready"

    assert "matched_requirements" in resume_sections
    assert "gap_requirements" in resume_sections
    assert "claims_needing_confirmation" in resume_sections
    assert "selection_rationale" in resume_sections
    assert "warnings" in resume_sections
    assert "selected_achievements" in resume_sections

    assert resume_sections["matched_requirements"]
    assert resume_sections["gap_requirements"]
    assert isinstance(resume_sections["claims_needing_confirmation"], list)
    assert isinstance(resume_sections["selection_rationale"], list)
    assert isinstance(resume_sections["warnings"], list)

    assert "FIT SUMMARY" not in (resume_document.rendered_text or "")
    assert "REVIEW NOTES" not in (resume_document.rendered_text or "")

    cover_letter_content = cover_letter_document.content_json
    cover_letter_sections = cover_letter_content["sections"]

    assert cover_letter_content["document_kind"] == "cover_letter"
    assert cover_letter_content["draft_mode"] == "deterministic_v1_review_ready"

    assert "matched_keywords" in cover_letter_sections
    assert "missing_keywords" in cover_letter_sections
    assert "matched_requirements" in cover_letter_sections
    assert "gap_requirements" in cover_letter_sections
    assert "selected_achievements" in cover_letter_sections
    assert "claims_needing_confirmation" in cover_letter_sections
    assert "warnings" in cover_letter_sections

    assert cover_letter_sections["matched_requirements"]
    assert cover_letter_sections["gap_requirements"]
    assert isinstance(cover_letter_sections["claims_needing_confirmation"], list)
    assert isinstance(cover_letter_sections["warnings"], list)

    rendered_letter = cover_letter_document.rendered_text or ""
    assert "profile does not strongly support" not in rendered_letter
    assert "cover letter draft should be reviewed" not in rendered_letter
    assert "needs_confirmation" not in rendered_letter