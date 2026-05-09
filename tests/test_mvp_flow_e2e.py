from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


API_PREFIX = "/api/v1"


async def test_mvp_flow_e2e(client):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded = upload_response.json()
    assert uploaded["file_kind"] == "resume"
    source_file_id = uploaded["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    imported = import_response.json()
    assert imported["text_length"] > 0
    extraction_id = imported["extraction_id"]

    structured_response = await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    assert structured_response.status_code == 200, structured_response.text
    structured = structured_response.json()
    assert structured["profile_id"]
    assert structured["experience_count"] >= 1

    achievements_response = await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )
    assert achievements_response.status_code == 200, achievements_response.text
    achievements = achievements_response.json()
    assert achievements["achievement_count"] >= 1

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "AI Product Engineer",
            "company": "Acme",
            "location": "Remote",
            "description_raw": (
                "Требования\n"
                "- Python\n"
                "- SQL\n"
                "- FastAPI\n"
                "- Docker\n"
                "- LLM\n\n"
                "Будет плюсом\n"
                "- Redis\n"
                "- PostgreSQL\n"
            ),
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy = vacancy_response.json()
    vacancy_id = vacancy["vacancy_id"]
    assert vacancy["id"] == vacancy_id
    assert "description_raw" not in vacancy
    assert "normalized_json" not in vacancy

    get_vacancy_response = await client.get(f"{API_PREFIX}/vacancies/{vacancy_id}")
    assert get_vacancy_response.status_code == 200, get_vacancy_response.text
    vacancy_read = get_vacancy_response.json()
    assert vacancy_read["id"] == vacancy_id
    assert vacancy_read["description_raw"]
    assert vacancy_read["description_length"] == len(vacancy_read["description_raw"])
    assert "normalized_json" not in vacancy_read
    assert "user_id" not in vacancy_read

    analysis_response = await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")
    assert analysis_response.status_code == 200, analysis_response.text
    analysis = analysis_response.json()
    assert analysis["analysis_version"] == "deterministic_v1"
    assert "Python" in analysis["keywords"]

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    resume = resume_response.json()
    resume_document_id = resume["document_id"]
    assert "content_json" not in resume
    assert "rendered_text" not in resume
    assert "rendered_text_preview" in resume
    assert len(resume["rendered_text_preview"]) <= 1200

    get_resume_response = await client.get(f"{API_PREFIX}/documents/{resume_document_id}")
    assert get_resume_response.status_code == 200, get_resume_response.text
    resume_read = get_resume_response.json()
    assert resume_read["id"] == resume_document_id
    assert resume_read["document_kind"] == "resume"
    assert resume_read["rendered_text"]
    assert "content_json" not in resume_read
    assert "FIT SUMMARY" not in resume_read["rendered_text"]
    assert "REVIEW NOTES" not in resume_read["rendered_text"]
    assert "Match score" not in resume_read["rendered_text"]
    assert "user_id" not in resume_read
    assert "derived_from_id" not in resume_read

    cover_letter_response = await client.post(
        f"{API_PREFIX}/documents/letters/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert cover_letter_response.status_code == 200, cover_letter_response.text
    cover_letter = cover_letter_response.json()
    cover_letter_document_id = cover_letter["document_id"]
    assert "content_json" not in cover_letter
    assert "rendered_text" not in cover_letter
    assert "rendered_text_preview" in cover_letter
    assert len(cover_letter["rendered_text_preview"]) <= 1200

    get_cover_letter_response = await client.get(
        f"{API_PREFIX}/documents/{cover_letter_document_id}"
    )
    assert get_cover_letter_response.status_code == 200, get_cover_letter_response.text
    cover_letter_read = get_cover_letter_response.json()
    assert cover_letter_read["id"] == cover_letter_document_id
    assert cover_letter_read["document_kind"] == "cover_letter"
    assert cover_letter_read["rendered_text"]
    assert "content_json" not in cover_letter_read
    assert "user_id" not in cover_letter_read
    assert "derived_from_id" not in cover_letter_read
    assert "profile does not strongly support" not in cover_letter_read["rendered_text"]
    assert "cover letter draft should be reviewed" not in cover_letter_read["rendered_text"]
    assert "needs_confirmation" not in cover_letter_read["rendered_text"]

    approve_resume_response = await client.patch(
        f"{API_PREFIX}/documents/{resume_document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "resume approved in test",
            "set_active_when_approved": True,
        },
    )
    assert approve_resume_response.status_code == 200, approve_resume_response.text
    assert approve_resume_response.json()["is_active"] is True

    approve_letter_response = await client.patch(
        f"{API_PREFIX}/documents/{cover_letter_document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "letter approved in test",
            "set_active_when_approved": True,
        },
    )
    assert approve_letter_response.status_code == 200, approve_letter_response.text
    assert approve_letter_response.json()["is_active"] is True

    create_application_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_document_id,
            "cover_letter_document_id": cover_letter_document_id,
            "notes": "Prepared for manual submission",
        },
    )
    assert create_application_response.status_code == 200, create_application_response.text
    application = create_application_response.json()
    application_id = application["id"]
    assert application["status"] == "draft"
    assert application["resume_document_id"] == resume_document_id
    assert application["cover_letter_document_id"] == cover_letter_document_id

    duplicate_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "notes": "Prepared for manual submission",
        },
    )
    assert duplicate_response.status_code == 409, duplicate_response.text
    assert duplicate_response.json()["detail"] == "application already exists for this vacancy"

    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "Ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text

    update_status_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "applied",
            "notes": "Submitted manually on HH",
        },
    )
    assert update_status_response.status_code == 200, update_status_response.text
    updated_application = update_status_response.json()
    assert updated_application["status"] == "applied"
    assert updated_application["applied_at"] is not None
    assert updated_application["notes"] == "Submitted manually on HH"

    list_response = await client.get(f"{API_PREFIX}/applications")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == application_id
    assert items[0]["status"] == "applied"
