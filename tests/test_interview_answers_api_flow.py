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


async def _create_interview_session(client) -> str:
    await _prepare_profile(client)

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

    create_response = await client.post(
        f"{API_PREFIX}/interviews/sessions",
        json={
            "vacancy_id": vacancy_id,
            "session_type": "vacancy",
        },
    )
    assert create_response.status_code == 200, create_response.text

    return create_response.json()["id"]


async def test_interview_answers_api_saves_answers_and_feedback(client) -> None:
    session_id = await _create_interview_session(client)

    response = await client.patch(
        f"{API_PREFIX}/interviews/sessions/{session_id}/answers",
        json={
            "answers": [
                {
                    "question_index": 0,
                    "answer_text": "I am interested in this role because it matches my Python background.",
                },
                {
                    "question_index": 1,
                    "answer_text": "I used Python in a practical project.",
                },
            ]
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["status"] == "answered"
    assert len(payload["answers"]) == 2
    assert payload["feedback"]["feedback_version"] == "deterministic_v1"
    assert payload["score"]["score_version"] == "deterministic_v2"
    assert payload["score"]["question_count"] >= 2
    assert payload["score"]["answered_count"] == 2
    assert payload["score"]["unanswered_count"] == payload["score"]["question_count"] - 2

    read_response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{session_id}",
    )
    assert read_response.status_code == 200, read_response.text
    read_payload = read_response.json()

    assert read_payload["status"] == "answered"
    assert read_payload["answers"] == payload["answers"]
    assert read_payload["feedback"] == payload["feedback"]


async def test_interview_answers_api_rejects_invalid_question_index(client) -> None:
    session_id = await _create_interview_session(client)

    response = await client.patch(
        f"{API_PREFIX}/interviews/sessions/{session_id}/answers",
        json={
            "answers": [
                {
                    "question_index": 999,
                    "answer_text": "Bad index",
                }
            ]
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "question_index out of range: 999"
