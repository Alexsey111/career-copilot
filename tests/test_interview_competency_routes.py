from __future__ import annotations

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


def _find_question(session_payload: dict, question_type: str, competency_key: str | None = None) -> dict:
    for question in session_payload["question_set"]:
        if question.get("type") != question_type:
            continue
        if competency_key is not None and question.get("competency_key") != competency_key:
            continue
        return question
    raise AssertionError(f"question not found: type={question_type}, competency_key={competency_key}")


async def test_get_competency_detail_returns_related_questions(client) -> None:
    created_session = await _create_session(client)
    must_have_question = _find_question(created_session, "must_have_requirement")
    competency_key = must_have_question["competency_key"]

    response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/competencies/{competency_key}",
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["competency"]["competency_key"] == competency_key
    assert payload["questions"]
    assert all(
        question.get("competency_key") == competency_key
        for question in payload["questions"]
    )


async def test_get_competency_detail_returns_answers_feedback_attempts(client) -> None:
    created_session = await _create_session(client)
    must_have_question = _find_question(created_session, "must_have_requirement")
    question_id = must_have_question["question_id"]
    competency_key = must_have_question["competency_key"]
    question_index = next(
        index
        for index, item in enumerate(created_session["question_set"])
        if item["question_id"] == question_id
    )

    update_response = await client.patch(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/answers",
        json={
            "answers": [
                {
                    "question_id": question_id,
                    "question_index": question_index,
                    "answer_text": "I used Python in a production backend project.",
                }
            ]
        },
    )
    assert update_response.status_code == 200, update_response.text

    attempt_response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/questions/{question_id}/attempts",
        json={
            "answer_text": (
                "Situation: we needed a backend service. Task: deliver an API. "
                "Action: I implemented Python endpoints. Result: the service launched."
            ),
            "update_session_answer": False,
        },
    )
    assert attempt_response.status_code == 200, attempt_response.text

    detail_response = await client.get(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/competencies/{competency_key}",
    )
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()

    assert any(answer["question_id"] == question_id for answer in payload["answers"])
    assert any(
        item["question_id"] == question_id for item in payload["feedback_items"]
    )
    assert any(attempt["question_id"] == question_id for attempt in payload["attempts"])


async def test_create_attempt_validates_question_id(client) -> None:
    created_session = await _create_session(client)

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/questions/iq_missing/attempts",
        json={
            "answer_text": "Some answer",
            "update_session_answer": True,
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "question_id not found in interview session"


async def test_create_attempt_creates_attempt(client, db_session) -> None:
    created_session = await _create_session(client)
    question = _find_question(created_session, "must_have_requirement")

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/questions/{question['question_id']}/attempts",
        json={
            "answer_text": (
                "Situation: we needed a backend. Task: build an API. "
                "Action: I used Python. Result: stable release."
            ),
            "update_session_answer": False,
        },
    )

    assert response.status_code == 200, response.text

    result = await db_session.execute(
        select(InterviewAnswerAttempt).where(
            InterviewAnswerAttempt.session_id == UUID(created_session["id"])
        )
    )
    attempts = result.scalars().all()
    assert len(attempts) == 1
    assert attempts[0].question_id == question["question_id"]


async def test_create_attempt_updates_session_answers(client) -> None:
    created_session = await _create_session(client)
    question = _find_question(created_session, "must_have_requirement")

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/questions/{question['question_id']}/attempts",
        json={
            "answer_text": (
                "Situation: we needed a backend. Task: build an API. "
                "Action: I used Python. Result: stable release."
            ),
            "update_session_answer": True,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert any(
        answer["question_id"] == question["question_id"]
        and answer["answer_text"]
        for answer in payload["answers"]
    )


async def test_create_attempt_recalculates_competency_readiness(client) -> None:
    created_session = await _create_session(client)
    question = _find_question(created_session, "must_have_requirement")
    competency_key = question["competency_key"]

    response = await client.post(
        f"{API_PREFIX}/interviews/sessions/{created_session['id']}/questions/{question['question_id']}/attempts",
        json={
            "answer_text": (
                "Situation: we needed a backend. Task: build an API. "
                "Action: I used Python in production. Result: stable release."
            ),
            "update_session_answer": True,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    competency = next(
        item
        for item in payload["score"]["competency_readiness"]
        if item["competency_key"] == competency_key
    )
    assert competency["answered_count"] >= 1
    assert competency["readiness_score"] is not None


async def test_interview_coach_advisory_route_returns_structured_response(
    client,
    monkeypatch,
) -> None:
    created_session = await _create_session(client)
    question = _find_question(created_session, "must_have_requirement")
    session_id = created_session["id"]

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
        assert competency["competency_key"] == question["competency_key"]
        assert answer == "I used Python in backend services."
        assert isinstance(evaluation, dict)
        return {
            "strong_parts": ["Mentions Python"],
            "missing_signals": ["No result"],
            "star_improvements": ["Add outcome"],
            "specificity_gaps": ["No metrics"],
            "risk_warnings": ["Needs confirmation"],
            "suggested_revision": "Situation ... Result ...",
            "confirmation_needed": ["Confirm production scope"],
        }

    from app.api.routes import interviews as interviews_route_module

    monkeypatch.setattr(
        interviews_route_module.InterviewPreparationService,
        "coach_answer_advisory",
        fake_coach_answer_advisory,
    )
    app.dependency_overrides[get_ai_orchestrator] = lambda: sentinel

    try:
        response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/coach/advisory",
            json={
                "question_id": question["question_id"],
                "answer_text": "I used Python in backend services.",
            },
        )
    finally:
        app.dependency_overrides.pop(get_ai_orchestrator, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["strong_parts"] == ["Mentions Python"]
    assert payload["missing_signals"] == ["No result"]
    assert payload["suggested_revision"] == "Situation ... Result ..."


async def test_interview_coach_advisory_does_not_create_attempt(
    client,
    db_session,
    monkeypatch,
) -> None:
    created_session = await _create_session(client)
    question = _find_question(created_session, "must_have_requirement")
    session_id = created_session["id"]

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
        return {
            "strong_parts": [],
            "missing_signals": [],
            "star_improvements": [],
            "specificity_gaps": [],
            "risk_warnings": [],
            "suggested_revision": "Keep refining",
            "confirmation_needed": [],
        }

    from app.api.routes import interviews as interviews_route_module

    monkeypatch.setattr(
        interviews_route_module.InterviewPreparationService,
        "coach_answer_advisory",
        fake_coach_answer_advisory,
    )
    app.dependency_overrides[get_ai_orchestrator] = lambda: object()

    try:
        response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/coach/advisory",
            json={
                "question_id": question["question_id"],
                "answer_text": "I used Python in backend services.",
            },
        )
    finally:
        app.dependency_overrides.pop(get_ai_orchestrator, None)

    assert response.status_code == 200, response.text

    result = await db_session.execute(
        select(InterviewAnswerAttempt).where(
            InterviewAnswerAttempt.session_id == UUID(session_id)
        )
    )
    attempts = result.scalars().all()
    assert attempts == []


async def test_interview_coach_advisory_validates_question_id(
    client,
    monkeypatch,
) -> None:
    created_session = await _create_session(client)
    session_id = created_session["id"]

    app.dependency_overrides[get_ai_orchestrator] = lambda: object()

    try:
        response = await client.post(
            f"{API_PREFIX}/interviews/sessions/{session_id}/coach/advisory",
            json={
                "question_id": "iq_missing",
                "answer_text": "Some answer",
            },
        )
    finally:
        app.dependency_overrides.pop(get_ai_orchestrator, None)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "question_id not found in interview session"
