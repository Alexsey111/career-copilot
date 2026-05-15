from __future__ import annotations

import pytest
from sqlalchemy import select
from uuid import UUID

from app.models import DocumentVersion, ImpactMeasurement, Recommendation


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


@pytest.mark.asyncio
async def test_execution_events_api_returns_timeline(client, db_session, test_user):
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    document_id = resume_response.json()["document_id"]

    create_response = await client.post(
        f"{API_PREFIX}/career-copilot/run",
        json={
            "user_id": str(test_user.id),
            "document_id": document_id,
            "vacancy_id": vacancy_id,
            "pipeline_version": "v1.0",
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_payload = create_response.json()
    execution_id = UUID(run_payload["id"])
    recommendation_id = run_payload["artifacts_json"]["recommendation_id"]
    mutated_document_id = UUID(run_payload["artifacts_json"]["mutated_document_id"])

    recommendation_rows = (
        await db_session.execute(
            select(Recommendation).where(Recommendation.execution_id == execution_id)
        )
    ).scalars().all()
    assert recommendation_rows, "Expected persistent recommendations for the execution"
    assert any(str(row.id) == recommendation_id for row in recommendation_rows)

    impact_row = (
        await db_session.execute(
            select(ImpactMeasurement).where(ImpactMeasurement.recommendation_id == recommendation_id)
        )
    ).scalar_one_or_none()
    assert impact_row is not None

    mutated_document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == mutated_document_id)
        )
    ).scalar_one_or_none()
    assert mutated_document is not None
    mutation_history = mutated_document.content_json.get("mutation_history", [])
    assert mutation_history, "Expected mutation history in mutated document"
    assert recommendation_id in mutation_history[-1]["reason"]

    events_response = await client.get(f"{API_PREFIX}/executions/{execution_id}/events")
    assert events_response.status_code == 200

    events = events_response.json()
    assert len(events) >= 3
    assert events[0]["event_type"] == "execution_started"
    assert any(event["event_type"] == "recommendation_applied" for event in events)
    assert events[-1]["event_type"] == "execution_completed"
    assert "created_at" in events[0]
