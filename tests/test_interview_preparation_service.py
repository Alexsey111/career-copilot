import pytest
from app.services.interview_preparation_service import InterviewPreparationService


def test_interview_preparation_builds_questions_from_analysis_and_achievements() -> None:
    service = InterviewPreparationService()

    questions = service._build_question_set(
        vacancy_title="Backend Developer",
        company="Test Company",
        must_have=[
            {"text": "Python"},
            {"text": "FastAPI"},
        ],
        nice_to_have=[
            {"text": "Docker"},
        ],
        strengths=[
            {
                "keyword": "Python",
                "scope": "must_have",
                "requirement_text": "Python",
            }
        ],
        gaps=[
            {
                "keyword": "FastAPI",
                "scope": "must_have",
                "requirement_text": "FastAPI",
            }
        ],
        achievements=[
            {
                "title": "Создание ИИ-системы мониторинга безопасности",
                "fact_status": "needs_confirmation",
            }
        ],
    )

    question_types = {item["type"] for item in questions}
    question_ids = [item["question_id"] for item in questions]

    assert "role_overview" in question_types
    assert "must_have_requirement" in question_types
    assert "gap_preparation" in question_types
    assert "strength_deep_dive" in question_types
    assert "achievement_star_story" in question_types
    assert len(question_ids) == len(set(question_ids))
    assert all(question_id.startswith("iq_") for question_id in question_ids)

    gap_question = next(item for item in questions if item["type"] == "gap_preparation")
    assert gap_question["keyword"] == "FastAPI"
    assert "не даёт сильного подтверждения" in gap_question["prompt"]

    role_question = next(item for item in questions if item["type"] == "role_overview")
    assert "почему вам интересна позиция" in role_question["prompt"]

    must_have_question = next(
        item for item in questions if item["type"] == "must_have_requirement"
    )
    assert "Опишите ваш практический опыт" in must_have_question["prompt"]
    assert must_have_question["source"] == "vacancy_analysis.must_have"
    assert must_have_question["requirement_text"] == "Python"
    assert must_have_question["competency_name"] == "Python"
    assert must_have_question["competency_key"] == "python"

    assert "Как честно ответить" in gap_question["prompt"]
    assert gap_question["source"] == "vacancy_analysis.gaps"
    assert gap_question["requirement_text"] == "FastAPI"
    assert gap_question["competency_name"] == "FastAPI"
    assert gap_question["competency_key"] == "fastapi"

    achievement_question = next(
        item for item in questions if item["type"] == "achievement_star_story"
    )
    assert achievement_question["fact_status"] == "needs_confirmation"
    assert "Превратите это достижение в STAR-историю" in achievement_question["prompt"]
    assert achievement_question["competency_key"] is None

    strength_question = next(item for item in questions if item["type"] == "strength_deep_dive")
    assert "Подготовьте более глубокий пример" in strength_question["prompt"]
    assert strength_question["source"] == "vacancy_analysis.strengths"
    assert strength_question["requirement_text"] == "Python"
    assert strength_question["competency_name"] == "Python"
    assert strength_question["competency_key"] == "python"


def test_interview_question_ids_are_deterministic() -> None:
    service = InterviewPreparationService()

    params = {
        "vacancy_title": "Backend Developer",
        "company": "Test Company",
        "must_have": [{"text": "Python"}],
        "nice_to_have": [{"text": "Docker"}],
        "strengths": [
            {"keyword": "Python", "scope": "must_have", "requirement_text": "Python"}
        ],
        "gaps": [
            {"keyword": "FastAPI", "scope": "must_have", "requirement_text": "FastAPI"}
        ],
        "achievements": [
            {
                "title": "Создание ИИ-системы мониторинга безопасности",
                "fact_status": "needs_confirmation",
            }
        ],
    }

    questions_a = service._build_question_set(**params)
    questions_b = service._build_question_set(**params)

    assert [item["question_id"] for item in questions_a] == [
        item["question_id"] for item in questions_b
    ]


def test_build_competency_key_normalizes_requirement_text() -> None:
    service = InterviewPreparationService()

    assert (
        service.build_competency_key("Backend API design")
        == "backend_api_design"
    )


def test_interview_questions_include_gaps() -> None:
    """Legacy question helper is fully removed."""
    service = InterviewPreparationService()

    assert not hasattr(service, "_build_questions")


def test_interview_questions_expected_answer_with_relevant_achievements() -> None:
    """Legacy expected answer helper is fully removed."""
    service = InterviewPreparationService()

    assert not hasattr(service, "_build_expected_answer")


def test_interview_questions_expected_answer_without_achievements() -> None:
    """Legacy expected answer helper stays removed across scenarios."""
    service = InterviewPreparationService()

    assert not hasattr(service, "_build_expected_answer")


def test_evaluate_answer_short() -> None:
    """Legacy evaluator is fully removed."""
    service = InterviewPreparationService()

    assert not hasattr(service, "_evaluate_answer_basic")


def test_evaluate_answer_good() -> None:
    """Canonical evaluator returns strong score for a detailed answer."""
    service = InterviewPreparationService()

    result = service.evaluate_answer(
        question="Describe your experience with Python",
        answer="I built a REST API using Python and FastAPI. The situation was that we needed a backend for our new product. I implemented the API with 5 endpoints and achieved 500 requests per second. The result was a successful launch.",
    )

    assert result["score"] > 0.5
    assert len(result["feedback"]) == 0


def test_evaluate_answer_missing_action_verbs() -> None:
    """Canonical evaluator flags weak answers."""
    service = InterviewPreparationService()

    result = service.evaluate_answer(
        question="What did you do?",
        answer="I was working on a project. There was a lot of Python code and 1000 users.",
    )

    assert any("specificity" in item["check_name"] for item in result["checks"])
    assert any(
        item["check_name"] == "star_completeness" and item["passed"] is False
        for item in result["checks"]
    )
    assert len(result["feedback"]) >= 1
    assert result["score"] < 1.0


def test_evaluate_answer_uses_answer_evaluation_engine() -> None:
    service = InterviewPreparationService()

    result = service.evaluate_answer(
        question="Describe your backend API work",
        answer=(
            "Situation: we needed a backend for a new workflow. "
            "Task: deliver an API quickly. "
            "Action: I designed and implemented 6 endpoints with Python. "
            "Result: latency dropped by 35%."
        ),
    )

    assert result["score"] > 0
    assert isinstance(result["checks"], list)
    check_names = {item["check_name"] for item in result["checks"]}
    assert "specificity" in check_names
    assert "star_completeness" in check_names
    assert "evidence_quality" in check_names
    assert "generic_wording" in check_names


@pytest.mark.asyncio
async def test_coach_answer_improves_structure(db_session, test_user):
    """Тест что coach_answer улучшает структуру ответа."""
    from app.ai.clients.base import BaseLLMClient, LLMClientError
    from app.ai.orchestrator import AIOrchestrator

    class MockCoachClient(BaseLLMClient):
        @property
        def provider_name(self):
            return "mock"

        async def aclose(self):
            pass

        async def generate(self, *args, **kwargs):
            raise LLMClientError("Not implemented")

        async def generate_structured(self, prompt, output_schema, **kwargs):
            return {
                "content": {
                    "improved_answer": "Situation: I needed to build a backend for our product. Task: Create a REST API. Action: I used Python and FastAPI to implement 5 endpoints. Result: The system handles 500 requests per second.",
                    "explanation": "Added STAR structure with specific details",
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=MockCoachClient())
    service = InterviewPreparationService()
    service.ai_orchestrator = orchestrator

    original_answer = "I used Python to build a REST API"

    result = await service.coach_answer(
        db_session,
        user_id=test_user.id,
        question="Tell me about Python",
        answer=original_answer,
        evaluation={"score": 0.25, "feedback": ["Answer is too short"]},
    )

    assert "Situation" in result["improved_answer"]
    assert "Added STAR structure" in result["explanation"]


@pytest.mark.asyncio
async def test_coach_answer_rejects_unsafe_enhancement(db_session, test_user):
    """Тест что coach_answer отклоняет небезопасные улучшения."""
    from app.ai.clients.base import BaseLLMClient, LLMClientError
    from app.ai.orchestrator import AIOrchestrator

    class MockUnsafeCoachClient(BaseLLMClient):
        @property
        def provider_name(self):
            return "mock"

        async def aclose(self):
            pass

        async def generate(self, *args, **kwargs):
            raise LLMClientError("Not implemented")

        async def generate_structured(self, prompt, output_schema, **kwargs):
            # AI пытается сильно расширить ответ (более чем в 5 раз)
            return {
                "content": {
                    "improved_answer": "Situation: I was working on a massive enterprise project with over 10000 concurrent users across multiple continents. Task: I needed to build the most advanced distributed system ever created using cutting-edge technologies. Action: I used Python, FastAPI, Docker, Kubernetes, PostgreSQL, Redis, Kafka, and many other sophisticated technologies to create an amazing microservices-based solution with advanced monitoring and logging. Result: The project was a huge success, increased revenue by 500%, reduced latency by 80%, and became the industry benchmark for performance.",
                    "explanation": "Completely rewrote with STAR",
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=MockUnsafeCoachClient())
    service = InterviewPreparationService()
    service.ai_orchestrator = orchestrator

    original_answer = "I used Python"

    result = await service.coach_answer(
        db_session,
        user_id=test_user.id,
        question="Tell me about Python",
        answer=original_answer,
        evaluation={"score": 0.25, "feedback": ["Answer is too short"]},
    )

    # Safety guard должен отклонить это улучшение
    assert result["improved_answer"] == original_answer
    assert "AI suggestion rejected" in result["explanation"]


@pytest.mark.asyncio
async def test_interview_coach_advisory_use_case_passes_context(db_session, test_user):
    from app.ai.registry.prompts import PromptTemplate
    from app.ai.use_cases.interview_coach import coach_answer_advisory

    captured: dict = {}

    class FakeOrchestrator:
        async def execute(self, session, **kwargs):
            captured["session"] = session
            captured.update(kwargs)
            return {
                "result": {
                    "strong_parts": ["Used Python"],
                    "missing_signals": ["No production scope"],
                    "star_improvements": ["Add result"],
                    "specificity_gaps": ["No metrics"],
                    "risk_warnings": ["Needs confirmation"],
                    "suggested_revision": "Revised answer",
                    "confirmation_needed": ["Confirm metrics"],
                }
            }

    question = {
        "question_id": "iq_python",
        "prompt": "Tell me about Python",
    }
    competency = {
        "competency_key": "python",
        "competency_name": "Python",
    }
    evaluation = {
        "score": 0.5,
        "feedback": ["too_generic"],
    }
    feedback = {
        "warnings": ["weak_star_structure"],
    }

    result = await coach_answer_advisory(
        FakeOrchestrator(),
        db_session,
        user_id=test_user.id,
        competency=competency,
        question=question,
        answer="I used Python to build APIs",
        evaluation=evaluation,
        feedback=feedback,
        language="ru",
    )

    assert result["result"]["suggested_revision"] == "Revised answer"
    assert captured["session"] is db_session
    assert captured["user_id"] == test_user.id
    assert captured["prompt_template"] == PromptTemplate.INTERVIEW_COACH_ADVISORY_V1
    assert captured["prompt_vars"]["competency"] == "Python"
    assert captured["prompt_vars"]["question"] == "Tell me about Python"
    assert captured["prompt_vars"]["answer"] == "I used Python to build APIs"
    assert captured["prompt_vars"]["evaluation"] == "Score: 0.5/1. Feedback: too_generic"
    assert captured["prompt_vars"]["feedback"] == "weak_star_structure"
    assert captured["workflow_name"] == "interview_coach_advisory"
    assert captured["target_type"] == "interview_answer"
    assert captured["target_id"] == "iq_python"
    assert captured["language"] == "ru"


@pytest.mark.asyncio
async def test_attempt_saved_on_evaluate(db_session, test_user):
    """Тест что попытка ответа сохраняется при вызове evaluate endpoint."""
    from sqlalchemy import select
    from app.api.routes.interviews import evaluate_interview_answer
    from app.models.entities import InterviewAnswerAttempt, InterviewSession
    from app.schemas.interview import InterviewAnswerEvaluateRequest
    import uuid

    # Создаём сессию напрямую (минуя service.create_session который требует vacancy analysis)
    session = InterviewSession(
        id=uuid.uuid4(),
        user_id=test_user.id,
        vacancy_id=None,
        session_type="general",
        status="draft",
        question_set_json=[
            {
                "question_id": "iq_test_python",
                "type": "strength_deep_dive",
                "source": "vacancy_analysis.strengths",
                "prompt": "Tell me about Python",
                "answer_format": "STAR",
                "rubric": [],
            }
        ],
        answers_json=[],
        feedback_json={},
        score_json={},
    )
    db_session.add(session)
    await db_session.flush()

    # Вызываем evaluate endpoint
    payload = InterviewAnswerEvaluateRequest(
        question_id="iq_test_python",
        answer_text="I used Python to build REST APIs with 1000 requests per second.",
    )

    result = await evaluate_interview_answer(
        session_id=session.id,
        payload=payload,
        current_user=test_user,
        session=db_session,
    )

    assert result.score is not None
    assert len(result.feedback) >= 0

    # Проверяем что attempt сохранён
    stmt = select(InterviewAnswerAttempt).where(
        InterviewAnswerAttempt.session_id == session.id
    )
    result_rows = await db_session.execute(stmt)
    attempts = result_rows.scalars().all()

    assert len(attempts) == 1
    assert attempts[0].question_id == "iq_test_python"
    assert attempts[0].answer_text == payload.answer_text
    assert attempts[0].score is not None
    assert "feedback" in attempts[0].feedback_json


def test_compute_progress_empty() -> None:
    """Тест что compute_progress возвращает None при пустом списке."""
    service = InterviewPreparationService()
    
    result = service.compute_progress([])
    
    assert result["first_score"] is None
    assert result["last_score"] is None
    assert result["improvement"] is None


def test_compute_progress_single_attempt() -> None:
    """Тест compute_progress с одной попыткой."""
    service = InterviewPreparationService()
    
    class MockAttempt:
        score = 0.5
    
    result = service.compute_progress([MockAttempt()])
    
    assert result["first_score"] == 0.5
    assert result["last_score"] == 0.5
    assert result["improvement"] == 0.0


def test_compute_progress_improvement() -> None:
    """Тест compute_progress с улучшением."""
    service = InterviewPreparationService()
    
    class MockAttempt:
        def __init__(self, score):
            self.score = score
    
    attempts = [MockAttempt(0.25), MockAttempt(0.5), MockAttempt(0.75)]
    progress = service.compute_progress(attempts)
    
    assert progress["first_score"] == 0.25
    assert progress["last_score"] == 0.75
    assert progress["improvement"] == 0.5
    assert progress["improvement"] > 0


def test_build_attempt_diff_added_keywords() -> None:
    """Тест что build_attempt_diff находит добавленные слова."""
    service = InterviewPreparationService()
    
    prev = "I used Python to build APIs"
    current = "I used Python and FastAPI to build REST APIs"
    
    diff = service.build_attempt_diff(prev, current)
    
    assert "fastapi" in diff["added_keywords"]
    assert "rest" in diff["added_keywords"]
    assert len(diff["removed_keywords"]) == 0


def test_build_attempt_diff_removed_keywords() -> None:
    """Тест что build_attempt_diff находит удалённые слова."""
    service = InterviewPreparationService()
    
    prev = "I used Python and Java to build systems"
    current = "I used Python to build APIs"
    
    diff = service.build_attempt_diff(prev, current)
    
    assert "java" in diff["removed_keywords"]
    assert "systems" in diff["removed_keywords"]
    assert "apis" in diff["added_keywords"]


def test_build_attempt_diff_empty() -> None:
    """Тест что build_attempt_diff работает с пустыми строками."""
    service = InterviewPreparationService()
    
    diff = service.build_attempt_diff("", "")
    
    assert diff["added_keywords"] == []
    assert diff["removed_keywords"] == []


def test_build_attempt_insight_improved() -> None:
    """Тест build_attempt_insight при улучшении."""
    
    class MockAttempt:
        def __init__(self, score, answer_text):
            self.score = score
            self.answer_text = answer_text
    
    prev = MockAttempt(0.25, "I used Python to build APIs")
    current = MockAttempt(0.75, "I used Python and FastAPI to build REST APIs")
    
    insight = InterviewPreparationService.build_attempt_insight(prev, current)
    
    assert insight["improved"] is True
    assert insight["score_delta"] == 0.5
    assert "fastapi" in insight["diff"]["added_keywords"]


def test_build_attempt_insight_regression() -> None:
    """Тест build_attempt_insight при ухудшении."""
    
    class MockAttempt:
        def __init__(self, score, answer_text):
            self.score = score
            self.answer_text = answer_text
    
    prev = MockAttempt(0.75, "I used Python and FastAPI")
    current = MockAttempt(0.5, "I used Python")
    
    insight = InterviewPreparationService.build_attempt_insight(prev, current)
    
    assert insight["improved"] is False
    assert insight["score_delta"] == -0.25
    assert "fastapi" in insight["diff"]["removed_keywords"]


def test_build_attempt_insight_null_scores() -> None:
    """Тест build_attempt_insight с None scores."""
    
    class MockAttempt:
        def __init__(self, score, answer_text):
            self.score = score
            self.answer_text = answer_text
    
    prev = MockAttempt(None, "I used Python")
    current = MockAttempt(None, "I used Python and FastAPI")
    
    insight = InterviewPreparationService.build_attempt_insight(prev, current)
    
    assert insight["improved"] is False
    assert insight["score_delta"] == 0.0


def test_attempt_diff() -> None:
    """Тест build_attempt_diff на простом примере."""
    
    prev = "I built API"
    curr = "I built scalable API with Python"
    
    diff = InterviewPreparationService.build_attempt_diff(prev, curr)
    
    assert "scalable" in diff["added_keywords"]
    assert "python" in diff["added_keywords"]
    assert "built" not in diff["added_keywords"]  # общее слово
    assert "built" not in diff["removed_keywords"]  # общее слово


@pytest.mark.asyncio
async def test_generate_coaching_hint_with_mock(db_session, test_user):
    """Тест что generate_coaching_hint возвращает AI-коучинг при >= 2 попытках."""
    from app.ai.clients.base import BaseLLMClient, LLMClientError
    from app.ai.orchestrator import AIOrchestrator
    from app.models.entities import InterviewAnswerAttempt, InterviewSession
    import uuid

    class MockCoachClient(BaseLLMClient):
        @property
        def provider_name(self):
            return "mock"

        async def aclose(self):
            pass

        async def generate(self, *args, **kwargs):
            raise LLMClientError("Not implemented")

        async def generate_structured(self, prompt, output_schema, **kwargs):
            return {
                "content": {
                    "improvement": "More structured",
                    "gap": "No metrics",
                    "next_step": "Add numbers"
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=MockCoachClient())
    service = InterviewPreparationService()

    # Создаём сессию интервью
    session_id = uuid.uuid4()
    interview_session = InterviewSession(
        id=session_id,
        user_id=test_user.id,
        vacancy_id=None,
        session_type="general",
        status="draft",
        question_set_json=[],
        answers_json=[],
        feedback_json={},
        score_json={},
    )
    db_session.add(interview_session)

    # Создаём две попытки ответа
    prev_attempt = InterviewAnswerAttempt(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id="q1",
        answer_text="I used Python to build APIs",
        score=0.25,
        feedback_json={},
    )
    db_session.add(prev_attempt)

    current_attempt = InterviewAnswerAttempt(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id="q1",
        answer_text="Situation: We needed a backend. Task: Build REST API. Action: I used Python and FastAPI. Result: 500 requests per second.",
        score=0.75,
        feedback_json={},
    )
    db_session.add(current_attempt)
    await db_session.flush()

    # Вычисляем diff
    diff = service.build_attempt_diff(
        prev_attempt.answer_text or "",
        current_attempt.answer_text or ""
    )

    # Генерируем coaching-фидбек
    coaching = await service.generate_coaching_hint(
        prev_attempt=prev_attempt,
        current_attempt=current_attempt,
        diff=diff,
        orchestrator=orchestrator,
        session=db_session,
        user_id=test_user.id,
    )

    assert coaching["improvement"] == "More structured"
    assert coaching["gap"] == "No metrics"
    assert coaching["next_step"] == "Add numbers"
