# app\api\routes\interviews.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_ai_orchestrator, get_current_active_user
from app.ai.orchestrator import AIOrchestrator
from app.db.session import get_db_session
from app.models import User
from app.models.entities import InterviewAnswerAttempt
from app.schemas.interview import (
    InterviewCompetencyDetailResponse,
    InterviewAnswerEvaluateRequest,
    InterviewAnswerEvaluateResponse,
    InterviewAnswerImproveRequest,
    InterviewAnswerImproveResponse,
    InterviewAttemptProgressResponse,
    InterviewAnswersUpdateRequest,
    InterviewQuestionAttemptCreateRequest,
    InterviewSessionCreateRequest,
    InterviewSessionListItem,
    InterviewSessionRead,
)
from app.schemas.json_contracts import AttemptFeedbackSchema
from app.repositories.interview_session_repository import InterviewSessionRepository
from app.services.interview_preparation_service import InterviewPreparationService
    

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.get("/sessions", response_model=list[InterviewSessionListItem])
async def list_interview_sessions(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[InterviewSessionListItem]:
    service = InterviewPreparationService()
    items = await service.list_session_dashboard_items(
        session,
        user_id=current_user.id,
    )
    return [InterviewSessionListItem(**item) for item in items]
    

@router.post("/sessions", response_model=InterviewSessionRead)
async def create_interview_session(
    payload: InterviewSessionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewSessionRead:
    service = InterviewPreparationService()
    interview_session = await service.create_session(
        session,
        user_id=current_user.id,
        vacancy_id=payload.vacancy_id,
        session_type=payload.session_type,
    )
    return _to_read_model(interview_session)


@router.patch("/sessions/{session_id}/answers", response_model=InterviewSessionRead)
async def update_interview_answers(
    session_id: UUID,
    payload: InterviewAnswersUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewSessionRead:
    service = InterviewPreparationService()
    interview_session = await service.save_answers(
        session,
        session_id=session_id,
        user_id=current_user.id,
        answers=[
            item.model_dump()
            for item in payload.answers
        ],
    )
    return _to_read_model(interview_session)


@router.get("/sessions/{session_id}", response_model=InterviewSessionRead)
async def get_interview_session(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewSessionRead:
    service = InterviewPreparationService()
    interview_session = await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    return _to_read_model(interview_session)


@router.get(
    "/sessions/{session_id}/competencies/{competency_key}",
    response_model=InterviewCompetencyDetailResponse,
)
async def get_interview_competency_detail(
    session_id: UUID,
    competency_key: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewCompetencyDetailResponse:
    service = InterviewPreparationService()
    interview_session = await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    detail = await service.build_competency_detail(
        session,
        interview_session=interview_session,
        competency_key=competency_key,
    )
    return InterviewCompetencyDetailResponse(**detail)


def _to_read_model(interview_session) -> InterviewSessionRead:
    return InterviewSessionRead(
        id=interview_session.id,
        vacancy_id=interview_session.vacancy_id,
        session_type=interview_session.session_type,
        status=interview_session.status,
        question_set=interview_session.question_set_json,
        answers=interview_session.answers_json,
        feedback=interview_session.feedback_json,
        score=interview_session.score_json,
        created_at=interview_session.created_at,
        updated_at=interview_session.updated_at,
    )


@router.post(
    "/sessions/{session_id}/evaluate",
    response_model=InterviewAnswerEvaluateResponse,
    )
async def evaluate_interview_answer(
    session_id: UUID,
    payload: InterviewAnswerEvaluateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewAnswerEvaluateResponse:
    service = InterviewPreparationService()
    repo = InterviewSessionRepository()
    
    interview_session = await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )

    question = service.get_question_by_id(
        question_set=interview_session.question_set_json or [],
        question_id=payload.question_id,
    )

    evaluation = service.evaluate_answer(
        question=question.get("prompt") or question.get("question_text") or "",
        answer=payload.answer_text,
    )
    
    # Валидация JSON-контракта перед сохранением
    validated_feedback = AttemptFeedbackSchema(feedback=evaluation["feedback"])

    # Сохраняем попытку ответа
    await repo.create_attempt(
        session=session,
        session_id=session_id,
        question_id=payload.question_id,
        answer_text=payload.answer_text,
        score=evaluation["score"],
        feedback_json=validated_feedback.model_dump(),
    )
    await session.commit()
    
    return InterviewAnswerEvaluateResponse(
        score=evaluation["score"],
        feedback=evaluation["feedback"],
    )


@router.post(
    "/sessions/{session_id}/questions/{question_id}/attempts",
    response_model=InterviewSessionRead,
)
async def create_interview_question_attempt(
    session_id: UUID,
    question_id: str,
    payload: InterviewQuestionAttemptCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewSessionRead:
    service = InterviewPreparationService()
    repo = InterviewSessionRepository()

    interview_session = await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    question_set = interview_session.question_set_json or []
    question = service.get_question_by_id(
        question_set=question_set,
        question_id=question_id,
    )

    evaluation = service.evaluate_answer(
        question=question.get("prompt") or question.get("question_text") or "",
        answer=payload.answer_text,
    )
    validated_feedback = AttemptFeedbackSchema(feedback=evaluation["feedback"])

    await repo.create_attempt(
        session=session,
        session_id=session_id,
        question_id=question_id,
        answer_text=payload.answer_text,
        score=evaluation["score"],
        feedback_json=validated_feedback.model_dump(),
    )

    if not payload.update_session_answer:
        await session.commit()
        await session.refresh(interview_session)
        return _to_read_model(interview_session)

    updated_answers_by_question_id: dict[str, dict[str, str | int]] = {}
    for existing_answer in interview_session.answers_json or []:
        existing_question_id = existing_answer.get("question_id")
        if not existing_question_id:
            continue
        updated_answers_by_question_id[str(existing_question_id)] = {
            "question_id": str(existing_question_id),
            "question_index": int(existing_answer.get("question_index") or 0),
            "answer_text": str(existing_answer.get("answer_text") or ""),
        }

    question_index = next(
        index
        for index, item in enumerate(question_set)
        if item.get("question_id") == question_id
    )
    updated_answers_by_question_id[question_id] = {
        "question_id": question_id,
        "question_index": question_index,
        "answer_text": payload.answer_text,
    }

    updated_answers = sorted(
        updated_answers_by_question_id.values(),
        key=lambda item: int(item["question_index"]),
    )
    updated_session = await service.save_answers(
        session,
        session_id=session_id,
        user_id=current_user.id,
        answers=updated_answers,
    )
    return _to_read_model(updated_session)


@router.post(
    "/sessions/{session_id}/coach",
    response_model=InterviewAnswerImproveResponse,
)
async def coach_interview_answer(
    session_id: UUID,
    payload: InterviewAnswerImproveRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> InterviewAnswerImproveResponse:
    """
    AI-улучшает ответ на вопрос собеседования.
    
    Сначала выполняется детерминированная оценка, затем AI даёт улучшения.
    """
    service = InterviewPreparationService(ai_orchestrator=orchestrator)
    
    # Проверяем доступ к сессии
    await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    
    # 1. Детерминированная оценка
    evaluation = service.evaluate_answer(
        question=payload.question_text,
        answer=payload.answer_text,
    )
    
    # 2. AI-коуч с контекстом оценки и safety guard
    improvement = await service.coach_answer(
        session=session,
        user_id=current_user.id,
        question=payload.question_text,
        answer=payload.answer_text,
        evaluation=evaluation,
        language="ru",
    )
    
    return InterviewAnswerImproveResponse(
        improved_answer=improvement.get("improved_answer", ""),
        explanation=improvement.get("explanation", ""),
    )


@router.get(
    "/sessions/{session_id}/questions/{question_id}/progress",
    response_model=InterviewAttemptProgressResponse,
)
async def get_question_progress(
    session_id: UUID,
    question_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> InterviewAttemptProgressResponse:
    """
    Возвращает прогресс по ответу на конкретный вопрос.
    
    Возвращает:
    - attempts: список всех попыток
    - progress: first_score, last_score, improvement
    - last_diff: сравнение последних двух попыток
    - coaching: AI-фидбек при наличии >= 2 попыток
    """
    service = InterviewPreparationService()
    
    # Проверяем доступ к сессии
    await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    
    # Получаем все попытки для этого вопроса
    stmt = (
        select(InterviewAnswerAttempt)
        .where(InterviewAnswerAttempt.session_id == session_id)
        .where(InterviewAnswerAttempt.question_id == question_id)
        .order_by(InterviewAnswerAttempt.created_at.asc())
    )
    result = await session.execute(stmt)
    attempts = result.scalars().all()
    
    # Вычисляем прогресс
    progress = service.compute_progress(list(attempts))
    
    # Вычисляем diff между последними двумя попытками
    last_diff = None
    coaching = None
    if len(attempts) >= 2:
        last_diff = service.build_attempt_insight(attempts[-2], attempts[-1])
    
        # Генерируем coaching-фидбек
        diff = service.build_attempt_diff(
            attempts[-2].answer_text or "",
            attempts[-1].answer_text or ""
        )
        coaching = await service.generate_coaching_hint(
            prev_attempt=attempts[-2],
            current_attempt=attempts[-1],
            diff=diff,
            orchestrator=orchestrator,
            session=session,
            user_id=current_user.id,
        )
    
    return InterviewAttemptProgressResponse(
        attempts=[
            {
                "id": str(a.id),
                "answer_text": a.answer_text,
                "score": a.score,
                "feedback_json": a.feedback_json,
                "created_at": a.created_at.isoformat(),
            }
            for a in attempts
        ],
        progress=progress,
        last_diff=last_diff,
        coaching=coaching,
    )
