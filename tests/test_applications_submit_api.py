from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import DocumentVersion


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


async def _generate_and_approve_resume(
    client,
    vacancy_id: str,
    *,
    set_active_when_approved: bool = True,
) -> str:
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
            "review_comment": "approved in submit flow test",
            "set_active_when_approved": set_active_when_approved,
        },
    )
    assert approve_response.status_code == 200, approve_response.text

    return resume_document_id


async def _mark_application_ready(client, application_id: str) -> None:
    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "Ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text


async def test_submit_ready_application_applies_when_safety_allows(client) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    resume_document_id = await _generate_and_approve_resume(client, vacancy_id)

    create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_document_id,
            "notes": "submit happy path",
        },
    )
    assert create_response.status_code == 200, create_response.text
    application_id = create_response.json()["id"]

    await _mark_application_ready(client, application_id)

    submit_response = await client.post(
        f"{API_PREFIX}/applications/{application_id}/submit",
        json={
            "source": "manual",
            "external_link": "https://example.com/apply/123",
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    payload = submit_response.json()
    assert payload["status"] == "applied"
    assert payload["source"] == "manual"
    assert payload["external_link"] == "https://example.com/apply/123"
    assert payload["applied_at"] is not None


async def test_submit_ready_application_returns_409_when_safety_blocks(
    client,
    db_session,
) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    resume_document_id = await _generate_and_approve_resume(client, vacancy_id)

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(resume_document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {
        "claims_needing_confirmation": [{"claim_text": "Need proof"}],
        "selected_achievements": [{"metric_text": "Reduced latency by 20%"}],
    }
    content["evaluation"] = {"critical_failures": [], "coverage_gaps": []}
    content["review"] = {"latest_status": "approved"}
    document.content_json = content
    await db_session.commit()

    create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_document_id,
            "notes": "submit blocked path",
        },
    )
    assert create_response.status_code == 200, create_response.text
    application_id = create_response.json()["id"]

    await _mark_application_ready(client, application_id)

    submit_response = await client.post(
        f"{API_PREFIX}/applications/{application_id}/submit",
        json={"source": "manual"},
    )

    assert submit_response.status_code == 409, submit_response.text
    detail = submit_response.json()["detail"]
    assert detail["message"] == "application safety gate blocked submission"
    assert (
        "document has unresolved claims requiring confirmation"
        in detail["blockers"]
    )
    assert detail["document_id"] == resume_document_id


async def test_create_draft_application_still_allowed_without_safety(client) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "notes": "draft creation without submit safety",
        },
    )

    assert create_response.status_code == 200, create_response.text
    payload = create_response.json()
    assert payload["status"] == "draft"
    assert payload["resume_document_id"] is None
