from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.api.dependencies import get_ai_orchestrator
from app.main import app
from app.models.entities import InterviewAnswerAttempt


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


async def _create_session(client) -> dict:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    create_response = await client.post(
        f"{API_PREFIX}/interviews/sessions",
        json={"vacancy_id": vacancy_id, "session_type": "vacancy"},
    )
    assert create_response.status_code == 200, create_response.text
    return create_response.json()


async def test_evaluate_route_creates_attempt_and_commits(client, db_session, monkeypatch) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_id = created_session["question_set"][0]["question_id"]

    original_commit = db_session.commit
    commit_mock = AsyncMock(side_effect=original_commit)
    monkeypatch.setattr(db_session, "commit", commit_mock)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/evaluate",
        json={
            "question_id": question_id,
            "answer_text": (
                "Situation: we needed a backend. Task: deliver quickly. "
                "Action: I built 5 endpoints with Python. Result: 35% lower latency."
            ),
        },
    )

    assert response.status_code == 200, response.text
    commit_mock.assert_awaited()

    result = await db_session.execute(
        select(InterviewAnswerAttempt).where(
            InterviewAnswerAttempt.session_id == UUID(session_id)
        )
    )
    attempts = result.scalars().all()
    assert len(attempts) == 1


async def test_coach_route_receives_orchestrator(client, monkeypatch) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]

    sentinel = object()

    async def fake_coach_answer(self, session, *, user_id, question, answer, evaluation, language="ru"):
        assert self.ai_orchestrator is sentinel
        return {
            "improved_answer": "Improved answer",
            "explanation": "Used injected orchestrator",
        }

    from app.api.routes import interviews as interviews_route_module

    monkeypatch.setattr(
        interviews_route_module.InterviewPreparationService,
        "coach_answer",
        fake_coach_answer,
    )
    app.dependency_overrides[get_ai_orchestrator] = lambda: sentinel

    try:
        response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/coach",
            json={
                "question_text": "Tell me about backend APIs",
                "answer_text": "I used Python",
            },
        )
    finally:
        app.dependency_overrides.pop(get_ai_orchestrator, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["improved_answer"] == "Improved answer"
    assert payload["explanation"] == "Used injected orchestrator"
