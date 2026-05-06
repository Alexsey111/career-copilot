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

    assert "role_overview" in question_types
    assert "must_have_requirement" in question_types
    assert "gap_preparation" in question_types
    assert "strength_deep_dive" in question_types
    assert "achievement_star_story" in question_types

    gap_question = next(item for item in questions if item["type"] == "gap_preparation")
    assert gap_question["keyword"] == "FastAPI"
    assert "не даёт сильного подтверждения" in gap_question["prompt"]

    role_question = next(item for item in questions if item["type"] == "role_overview")
    assert "почему вам интересна позиция" in role_question["prompt"]

    must_have_question = next(
        item for item in questions if item["type"] == "must_have_requirement"
    )
    assert "Опишите ваш практический опыт" in must_have_question["prompt"]

    assert "Как честно ответить" in gap_question["prompt"]

    achievement_question = next(
        item for item in questions if item["type"] == "achievement_star_story"
    )
    assert achievement_question["fact_status"] == "needs_confirmation"
    assert "Превратите это достижение в STAR-историю" in achievement_question["prompt"]

    strength_question = next(item for item in questions if item["type"] == "strength_deep_dive")
    assert "Подготовьте более глубокий пример" in strength_question["prompt"]


def test_interview_questions_include_gaps() -> None:
    """Тест что _build_questions создаёт вопросы для gap-зон."""
    service = InterviewPreparationService()

    questions = service._build_questions(
        strengths=["Python"],
        gaps=["Docker"],
        achievements=[],
    )

    # Проверяем что есть gap вопрос
    assert any(q["type"] == "gap" for q in questions)

    # Проверяем что Docker упоминается в вопросе
    gap_question = next(q for q in questions if q["type"] == "gap")
    assert "Docker" in gap_question["question"]
    assert "less experience" in gap_question["question"].lower()
    assert "expected_answer" in gap_question


def test_interview_questions_expected_answer_with_relevant_achievements() -> None:
    """Тест что expected_answer использует релевантные достижения."""
    service = InterviewPreparationService()

    questions = service._build_questions(
        strengths=["Python"],
        gaps=["Docker"],
        achievements=["Создание Python сервиса", "Разработка Docker контейнеров"],
    )

    # Python вопрос должен ссылаться на Python достижение
    python_question = next(q for q in questions if q["skill"] == "Python")
    assert "Python" in python_question["expected_answer"]
    assert "STAR" in python_question["expected_answer"]

    # Docker вопрос тоже должен иметь expected_answer
    docker_question = next(q for q in questions if q["skill"] == "Docker")
    assert "STAR" in docker_question["expected_answer"]


def test_interview_questions_expected_answer_without_achievements() -> None:
    """Тест что при отсутствии достижений возвращается заглушка."""
    service = InterviewPreparationService()

    expected = service._build_expected_answer(
        skill="Kubernetes",
        achievements=[],
    )

    assert "Explain learning efforts" in expected
    assert "practical steps" in expected


def test_evaluate_answer_short() -> None:
    """Тест что короткий ответ получает низкую оценку."""
    service = InterviewPreparationService()

    result = service._evaluate_answer_basic(
        question="Tell me about Python",
        answer="I used Python",
    )

    assert result["score"] < 1
    assert "too short" in result["feedback"][0].lower()


def test_evaluate_answer_good() -> None:
    """Тест что хороший ответ с метриками и STAR получает высокую оценку."""
    service = InterviewPreparationService()

    result = service._evaluate_answer_basic(
        question="Describe your experience with Python",
        answer="I built a REST API using Python and FastAPI. The situation was that we needed a backend for our new product. I implemented the API with 5 endpoints and achieved 500 requests per second. The result was a successful launch.",
    )

    assert result["score"] == 1.0
    assert len(result["feedback"]) == 0


def test_evaluate_answer_missing_action_verbs() -> None:
    """Тест что ответ без глаголов действия получает фидбек."""
    service = InterviewPreparationService()

    result = service._evaluate_answer_basic(
        question="What did you do?",
        answer="I was working on a project. There was a lot of Python code and 1000 users.",
    )

    assert "Lacks strong action verbs" in result["feedback"]
    assert result["score"] < 1.0


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
        question_set_json=[],
        answers_json=[],
        feedback_json={},
        score_json={},
    )
    db_session.add(session)
    await db_session.flush()

    # Вызываем evaluate endpoint
    payload = InterviewAnswerEvaluateRequest(
        question_id="q1",
        question_text="Tell me about Python",
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
    assert attempts[0].question_id == "q1"
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
