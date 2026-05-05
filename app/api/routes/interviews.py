# app\api\routes\interviews.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.models.entities import InterviewAnswerAttempt
from app.schemas.interview import (
    InterviewAnswerEvaluateRequest,
    InterviewAnswerEvaluateResponse,
    InterviewAnswerImproveRequest,
    InterviewAnswerImproveResponse,
    InterviewAttemptProgressResponse,
    InterviewAnswersUpdateRequest,
    InterviewSessionCreateRequest,
    InterviewSessionListItem,
    InterviewSessionRead,
)
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


@router.post("/sessions/{session_id}/generate", response_model=InterviewSessionRead)
async def generate_interview_questions(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewSessionRead:
    """
    Генерирует вопросы для собеседования на основе strengths и gaps из анализа вакансии.
    
    Ключевая идея: gap → прямой вопрос "Как вы работаете над этим пробелом?"
    """
    service = InterviewPreparationService()
    
    # Получаем сессию
    interview_session = await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )

    # Получаем анализ вакансии для strengths/gaps
    vacancy_analysis = await service.vacancy_analysis_repository.get_latest_for_vacancy(
        session,
        interview_session.vacancy_id,
        user_id=current_user.id,
    )
    
    if vacancy_analysis is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vacancy analysis not found; run vacancy analysis first",
        )
    
    # Получаем профиль для достижений
    profile = await service.candidate_profile_repository.get_with_related_by_user_id(
        session,
        current_user.id,
    )
    
    if profile is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="candidate profile not found; run profile extraction first",
        )
    
    # Извлекаем strengths и gaps как списки строк
    strengths = [item.get("keyword", "") for item in vacancy_analysis.strengths_json if item.get("keyword")]
    gaps = [item.get("keyword", "") for item in vacancy_analysis.gaps_json if item.get("keyword")]
    achievements = [item.title for item in profile.achievements if item.title]
    
    # Генерируем вопросы с expected_answer
    question_set = service._build_questions(
        strengths=strengths,
        gaps=gaps,
        achievements=achievements,
    )
    
    # Сохраняем обновлённый question_set
    interview_session = await service.interview_session_repository.update_question_set(
        session,
        interview_session,
        question_set_json=question_set,
        status="generated",
    )
    
    await session.commit()
    await session.refresh(interview_session)
    return _to_read_model(interview_session)


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
    """
    Оценивает ответ на вопрос собеседования (детерминированно, без AI).
    
    Критерии:
    - Длина ответа (>20 слов)
    - Наличие цифр/метрик
    - Глаголы действия (built, implemented, designed, led)
    - Структура STAR (situation/result)
    """
    service = InterviewPreparationService()
    repo = InterviewSessionRepository()
    
    # Проверяем доступ к сессии
    await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    
    # Оценка ответа
    evaluation = service._evaluate_answer_basic(
        question=payload.question_text,
        answer=payload.answer_text,
    )
    
    # Сохраняем попытку ответа
    await repo.create_attempt(
        session=session,
        session_id=session_id,
        question_id=payload.question_id or payload.question_text[:50],
        answer_text=payload.answer_text,
        score=evaluation["score"],
        feedback_json={"feedback": evaluation["feedback"]},
    )
    
    return InterviewAnswerEvaluateResponse(
        score=evaluation["score"],
        feedback=evaluation["feedback"],
    )


@router.post(
    "/sessions/{session_id}/coach",
    response_model=InterviewAnswerImproveResponse,
)
async def coach_interview_answer(
    session_id: UUID,
    payload: InterviewAnswerImproveRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewAnswerImproveResponse:
    """
    AI-улучшает ответ на вопрос собеседования.
    
    Сначала выполняется детерминированная оценка, затем AI даёт улучшения.
    """
    service = InterviewPreparationService()
    
    # Проверяем доступ к сессии
    await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
    
    # 1. Детерминированная оценка
    evaluation = service._evaluate_answer_basic(
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
) -> InterviewAttemptProgressResponse:
    """
    Возвращает прогресс по ответу на конкретный вопрос.
    
    Возвращает:
    - attempts: список всех попыток
    - progress: first_score, last_score, improvement
    - last_diff: сравнение последних двух попыток
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
    if len(attempts) >= 2:
        last_diff = service.build_attempt_insight(attempts[-2], attempts[-1])
    
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
    )
