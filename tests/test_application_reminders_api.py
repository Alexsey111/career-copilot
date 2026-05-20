from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import update

from app.models import ApplicationRecord


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


async def _create_analyzed_vacancy(client, title: str) -> str:
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


async def _generate_and_approve_resume(client, vacancy_id: str) -> str:
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
            "review_comment": "approved in reminder test",
            "set_active_when_approved": True,
        },
    )
    assert approve_response.status_code == 200, approve_response.text

    return resume_document_id


async def _create_application(client, vacancy_id: str, resume_document_id: str) -> str:
    create_response = await client.post(
        f"{API_PREFIX}/applications",
        json={
            "vacancy_id": vacancy_id,
            "resume_document_id": resume_document_id,
            "notes": "reminder test",
        },
    )
    assert create_response.status_code == 200, create_response.text
    return create_response.json()["id"]


async def _mark_application_ready(client, application_id: str) -> None:
    ready_response = await client.patch(
        f"{API_PREFIX}/applications/{application_id}/status",
        json={
            "status": "ready",
            "notes": "Ready for submission",
        },
    )
    assert ready_response.status_code == 200, ready_response.text


async def _set_application_times(
    db_session,
    application_id: str,
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    applied_at: datetime | None = None,
) -> None:
    values: dict[str, datetime] = {}
    if created_at is not None:
        values["created_at"] = created_at
    if updated_at is not None:
        values["updated_at"] = updated_at
    if applied_at is not None:
        values["applied_at"] = applied_at

    assert values, "at least one timestamp value must be provided"

    await db_session.execute(
        update(ApplicationRecord)
        .where(ApplicationRecord.id == UUID(application_id))
        .values(**values)
    )
    await db_session.commit()


async def test_application_reminders_api_returns_stale_ready_and_follow_up_items(
    client,
    db_session,
) -> None:
    await _prepare_profile(client)

    draft_vacancy_id = await _create_analyzed_vacancy(client, "Backend Developer")
    draft_resume_document_id = await _generate_and_approve_resume(client, draft_vacancy_id)
    draft_application_id = await _create_application(client, draft_vacancy_id, draft_resume_document_id)
    old_created_at = datetime.now(timezone.utc) - timedelta(days=21)
    await _set_application_times(
        db_session,
        draft_application_id,
        created_at=old_created_at,
        updated_at=old_created_at,
    )

    ready_vacancy_id = await _create_analyzed_vacancy(client, "Platform Engineer")
    ready_resume_document_id = await _generate_and_approve_resume(client, ready_vacancy_id)
    ready_application_id = await _create_application(client, ready_vacancy_id, ready_resume_document_id)
    await _mark_application_ready(client, ready_application_id)
    old_updated_at = datetime.now(timezone.utc) - timedelta(days=10)
    await _set_application_times(
        db_session,
        ready_application_id,
        updated_at=old_updated_at,
    )

    applied_vacancy_id = await _create_analyzed_vacancy(client, "Data Engineer")
    applied_resume_document_id = await _generate_and_approve_resume(client, applied_vacancy_id)
    applied_application_id = await _create_application(client, applied_vacancy_id, applied_resume_document_id)
    await _mark_application_ready(client, applied_application_id)
    submit_response = await client.post(
        f"{API_PREFIX}/applications/{applied_application_id}/submit",
        json={"source": "manual"},
    )
    assert submit_response.status_code == 200, submit_response.text
    old_applied_at = datetime.now(timezone.utc) - timedelta(days=18)
    await _set_application_times(
        db_session,
        applied_application_id,
        applied_at=old_applied_at,
    )

    response = await client.get(f"{API_PREFIX}/applications/reminders")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert len(payload) == 3

    reminder_types = {item["reminder_type"] for item in payload}
    assert reminder_types == {
        "draft_stale",
        "ready_not_submitted",
        "follow_up_missing",
    }

    reminders_by_type = {item["reminder_type"]: item for item in payload}
    assert reminders_by_type["draft_stale"]["days_since_event"] >= 21
    assert reminders_by_type["ready_not_submitted"]["days_since_event"] >= 10
    assert reminders_by_type["follow_up_missing"]["days_since_event"] >= 18
    assert reminders_by_type["draft_stale"]["title"] == "Черновик без активности"
    assert reminders_by_type["ready_not_submitted"]["title"] == "Готов к отправке, но не отправлен"
    assert reminders_by_type["follow_up_missing"]["title"] == "Нет follow-up по отклику"
