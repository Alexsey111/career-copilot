# app\ai\use_cases\interview_coach.py

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


async def coach_answer(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    question: str,
    answer: str,
    evaluation: dict,
    language: str = "ru",
):
    """AI-коучинг ответа на вопрос собеседования.

    Сервис передаёт вопрос, ответ и детерминированную оценку;
    use case формирует prompt_vars и выбирает промпт.
    """
    evaluation_text = (
        f"Score: {evaluation.get('score', 0)}/1. "
        f"Feedback: {', '.join(evaluation.get('feedback', []))}"
    )

    return await orchestrator.execute(
        session=session,
        user_id=user_id,
        prompt_template=PromptTemplate.INTERVIEW_COACH_V1,
        prompt_vars={
            "question": question,
            "answer": answer,
            "evaluation": evaluation_text,
            "language": language,
        },
        workflow_name="interview_coach",
        target_type="interview_answer",
        language=language,
    )


async def coach_attempts(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    prev_attempt,
    current_attempt,
    diff: dict,
):
    """AI-коучинг между двумя попытками ответа.

    Сервис передаёт попытки и diff;
    use case вычисляет score_delta и выбирает промпт.
    """
    score_delta = (current_attempt.score or 0) - (prev_attempt.score or 0)

    return await orchestrator.execute(
        session=session,
        user_id=user_id,
        prompt_template=PromptTemplate.INTERVIEW_COACHING_V1,
        prompt_vars={
            "previous_answer": prev_attempt.answer_text or "",
            "current_answer": current_attempt.answer_text or "",
            "score_delta": str(score_delta),
            "added_keywords": diff["added_keywords"],
            "removed_keywords": diff["removed_keywords"],
        },
        workflow_name="interview_coaching",
        target_type="interview_session",
        target_id=str(current_attempt.session_id),
    )
