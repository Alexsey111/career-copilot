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


async def test_interview_session_list_returns_dashboard_fields(client) -> None:
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

    update_response = await client.patch(
        f"{API_PREFIX}/interviews/sessions/{session_id}/answers",
        json={
            "answers": [
                {
                    "question_index": 0,
                    "answer_text": "I am interested in this role because it matches my Python background.",
                },
                {
                    "question_index": 1,
                    "answer_text": (
                        "Ситуация: я работал над Python-проектом. "
                        "Задача: нужно было собрать backend-прототип. "
                        "Действия: я реализовал API-flow. "
                        "Результат: прототип прошёл smoke-проверку."
                    ),
                },
            ]
        },
    )
    assert update_response.status_code == 200, update_response.text

    list_response = await client.get(f"{API_PREFIX}/interviews/sessions")
    assert list_response.status_code == 200, list_response.text

    items = list_response.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    item = next(session for session in items if session["id"] == session_id)

    assert item["vacancy_id"] == vacancy_id
    assert item["vacancy_title"] == "Backend Developer"
    assert item["vacancy_company"] == "Test Company"
    assert item["vacancy_location"] == "Remote"
    assert item["session_type"] == "vacancy"
    assert item["status"] == "answered"
    assert item["question_count"] >= 2
    assert item["answered_count"] == 2
    assert item["unanswered_count"] == item["question_count"] - 2
    assert item["warning_count"] >= 0
    assert item["readiness_score"] is not None
    assert item["created_at"] is not None
    assert item["updated_at"] is not None