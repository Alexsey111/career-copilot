# app\api\routes\interviews.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_dev_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.interview import (
    InterviewAnswersUpdateRequest,
    InterviewSessionCreateRequest,
    InterviewSessionListItem,
    InterviewSessionRead,
)
from app.services.interview_preparation_service import InterviewPreparationService


router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.get("/sessions", response_model=list[InterviewSessionListItem])
async def list_interview_sessions(
    current_user: User = Depends(get_current_dev_user),
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
    current_user: User = Depends(get_current_dev_user),
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
    current_user: User = Depends(get_current_dev_user),
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
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewSessionRead:
    service = InterviewPreparationService()
    interview_session = await service.get_session(
        session,
        session_id=session_id,
        user_id=current_user.id,
    )
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
