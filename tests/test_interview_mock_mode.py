from __future__ import annotations

from app.api.dependencies import get_ai_orchestrator
from app.models.entities import InterviewSession
from app.main import app
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


async def _create_session(client) -> dict:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)
    create_response = await client.post(
        f"{API_PREFIX}/interviews/sessions",
        json={"vacancy_id": vacancy_id, "session_type": "vacancy"},
    )
    assert create_response.status_code == 200, create_response.text
    return create_response.json()


async def _start_mock_session(client, session_id: str) -> None:
    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/start",
    )
    assert response.status_code == 200, response.text


async def _complete_mock_session(client, session_id: str, question_set: list[dict]) -> dict:
    last_payload = {}
    for question in question_set:
        answer_response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
            json={
                "question_id": question["question_id"],
                "answer_text": (
                    "Situation: we needed a backend. Task: deliver a feature. "
                    "Action: I implemented the API. Result: it worked in production."
                ),
            },
        )
        assert answer_response.status_code == 200, answer_response.text
        last_payload = answer_response.json()
    return last_payload


async def test_start_mock_session(client) -> None:
    created_session = await _create_session(client)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/mock/start",
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["mode"] == "mock_interview"
    assert payload["current_question_index"] == 0
    assert payload["completed_at"] is None


async def test_current_question_requires_started_mock_session(client) -> None:
    created_session = await _create_session(client)

    response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/mock/current",
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "mock interview not started"


async def test_current_question_returned(client) -> None:
    created_session = await _create_session(client)
    question_set = created_session["question_set"]

    await _start_mock_session(client, created_session["id"])

    response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/mock/current",
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["question_index"] == 0
    assert payload["question"]["question_id"] == question_set[0]["question_id"]
    assert payload["progress"] == {"current": 1, "total": len(question_set)}


async def test_mock_answer_validates_current_question_id(client) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]

    await _start_mock_session(client, session_id)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
        json={
            "question_id": question_set[1]["question_id"],
            "answer_text": "Wrong question answer",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "question_id does not match current mock question"


async def test_mock_answer_creates_attempt_and_advances_pointer(client) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]

    await _start_mock_session(client, session_id)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
        json={
            "question_id": question_set[0]["question_id"],
            "answer_text": (
                "Situation: we needed a backend. Task: build an API. "
                "Action: I used Python and FastAPI. Result: stable release."
            ),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["completed"] is False
    assert payload["evaluation"]["score"] is not None
    assert payload["session"]["status"] == "in_progress"
    assert payload["session"]["mode"] == "mock_interview"
    assert payload["session"]["current_question_index"] == 1
    assert payload["session"]["score"]["readiness_score"] is not None
    assert payload["next_question"]["question_id"] == question_set[1]["question_id"]
    assert payload["progress"] == {"current": 2, "total": len(question_set)}
    assert any(
        answer["question_id"] == question_set[0]["question_id"]
        for answer in payload["session"]["answers"]
    )


async def test_mock_answer_last_question_completes_session(client) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]

    await _start_mock_session(client, session_id)

    last_payload = await _complete_mock_session(client, session_id, question_set)

    assert last_payload is not None
    assert last_payload["completed"] is True
    assert last_payload["session"]["status"] == "completed"
    assert last_payload["session"]["completed_at"] is not None
    assert last_payload["session"]["current_question_index"] is None
    assert last_payload["next_question"] is None

    summary_response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/summary",
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["session"]["status"] == "completed"
    assert summary["progress"]["completed"] is True
    assert summary["progress"]["answered"] == len(question_set)
    assert summary["progress"]["total"] == len(question_set)
    assert summary["attempt_count"] == len(question_set)
    assert isinstance(summary["weak_competencies"], list)
    assert isinstance(summary["competency_readiness"], list)


async def test_mock_answer_after_completed_returns_400(client) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]

    await _start_mock_session(client, session_id)

    await _complete_mock_session(client, session_id, question_set)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
        json={
            "question_id": question_set[-1]["question_id"],
            "answer_text": "Another answer",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "mock interview already completed"


async def test_mock_start_after_completed_returns_400(client) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]

    await _start_mock_session(client, session_id)
    await _complete_mock_session(client, session_id, question_set)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/start",
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "mock interview already completed"


async def test_mock_answer_rejects_invalid_pointer(client, db_session) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]

    await _start_mock_session(client, session_id)

    session_model = await db_session.get(InterviewSession, session_id)
    assert session_model is not None
    session_model.current_question_index = len(question_set) + 2
    await db_session.commit()
    await db_session.refresh(session_model)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
        json={
            "question_id": question_set[0]["question_id"],
            "answer_text": "Pointer is broken",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "current_question_index out of range"


async def test_mock_answer_include_advisory_does_not_autosave_ai_as_truth(
    client,
    monkeypatch,
) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]
    first_question = question_set[0]

    await _start_mock_session(client, session_id)

    sentinel = object()

    async def fake_coach_answer_advisory(
        self,
        session,
        *,
        user_id,
        competency,
        question,
        answer,
        evaluation,
        feedback=None,
        language="ru",
    ):
        assert self.ai_orchestrator is sentinel
        return {
            "strong_parts": ["Mentions Python"],
            "missing_signals": ["No result"],
            "star_improvements": ["Add outcome"],
            "specificity_gaps": ["No metrics"],
            "risk_warnings": ["Needs confirmation"],
            "suggested_revision": "AI rewritten answer that should not be autosaved",
            "confirmation_needed": ["Confirm scope"],
        }

    from app.api.routes import interviews as interviews_route_module

    monkeypatch.setattr(
        interviews_route_module.InterviewPreparationService,
        "coach_answer_advisory",
        fake_coach_answer_advisory,
    )
    monkeypatch.setattr(interviews_route_module, "get_ai_orchestrator", lambda: sentinel)
    app.dependency_overrides[get_ai_orchestrator] = lambda: sentinel

    try:
        response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
            json={
                "question_id": first_question["question_id"],
                "answer_text": "I used Python in backend services.",
                "include_advisory": True,
            },
        )
    finally:
        app.dependency_overrides.pop(get_ai_orchestrator, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["advisory"] is not None
    assert (
        payload["advisory"]["suggested_revision"]
        == "AI rewritten answer that should not be autosaved"
    )
    saved_answer = next(
        answer
        for answer in payload["session"]["answers"]
        if answer["question_id"] == first_question["question_id"]
    )
    assert saved_answer["answer_text"] == "I used Python in backend services."


async def test_question_order_stable(client) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]
    question_set = created_session["question_set"]
    expected_order = [item["question_id"] for item in question_set]

    await _start_mock_session(client, session_id)

    seen_order: list[str] = []
    for expected_question_id in expected_order:
        current_response = await client.get(
            f"{API_PREFIX}/interviews/sessions/{session_id}/mock/current",
        )
        assert current_response.status_code == 200, current_response.text
        current_payload = current_response.json()
        seen_order.append(current_payload["question"]["question_id"])

        answer_response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/mock/answer",
            json={
                "question_id": expected_question_id,
                "answer_text": (
                    "Situation: we needed a backend. Task: deliver a feature. "
                    "Action: I implemented the API. Result: it worked in production."
                ),
            },
        )
        assert answer_response.status_code == 200, answer_response.text

    assert seen_order == expected_order
