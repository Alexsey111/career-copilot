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


async def test_interview_session_api_creates_and_reads_preparation_session(client) -> None:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    create_response = await client.post(
        f"{API_PREFIX}/interviews/sessions",
        json={
            "vacancy_id": vacancy_id,
            "session_type": "vacancy",
        },
    )
    assert create_response.status_code == 200, create_response.text

    created = create_response.json()
    session_id = created["id"]

    assert created["vacancy_id"] == vacancy_id
    assert created["session_type"] == "vacancy"
    assert created["status"] == "draft"
    assert created["question_set"]
    assert created["answers"] == []
    assert created["feedback"] == {}
    assert created["score"] == {}

    question_types = {item["type"] for item in created["question_set"]}
    assert "role_overview" in question_types
    assert "must_have_requirement" in question_types
    assert "gap_preparation" in question_types
    assert "strength_deep_dive" in question_types
    assert "achievement_star_story" in question_types

    read_response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{session_id}",
    )
    assert read_response.status_code == 200, read_response.text
    read = read_response.json()

    assert read["id"] == session_id
    assert read["vacancy_id"] == vacancy_id
    assert read["question_set"] == created["question_set"]


async def test_interview_session_api_requires_vacancy_analysis(client) -> None:
    await _prepare_profile(client)

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "description_raw": "Backend developer, Python, FastAPI",
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy_id = vacancy_response.json()["vacancy_id"]

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions",
        json={
            "vacancy_id": vacancy_id,
            "session_type": "vacancy",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "vacancy analysis not found; run vacancy analysis first"