# app\api\routes\evidence.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.interview_prep import (
    InterviewPrepReadinessRead,
    InterviewPrepSessionCreateRequest,
    InterviewPrepSessionListItem,
    InterviewPrepSessionRead,
)
from app.services.interview_prep_service import InterviewPrepService


router = APIRouter(prefix="/interview-prep", tags=["interview-prep"])


@router.get("/sessions", response_model=list[InterviewPrepSessionListItem])
async def list_interview_prep_sessions(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[InterviewPrepSessionListItem]:
    service = InterviewPrepService()
    items = await service.list_sessions(session, user_id=current_user.id)
    return [InterviewPrepSessionListItem(**item) for item in items]


@router.post("/sessions", response_model=InterviewPrepSessionRead)
async def create_interview_prep_session(
    payload: InterviewPrepSessionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewPrepSessionRead:
    service = InterviewPrepService()
    prep_session = await service.create_session(
        session,
        user_id=current_user.id,
        application_id=payload.application_id,
    )
    return _to_read_model(prep_session)


@router.get("/sessions/{prep_session_id}", response_model=InterviewPrepSessionRead)
async def get_interview_prep_session(
    prep_session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewPrepSessionRead:
    service = InterviewPrepService()
    prep_session = await service.get_session(
        session,
        prep_session_id=prep_session_id,
        user_id=current_user.id,
    )
    return _to_read_model(prep_session)


@router.get(
    "/sessions/{prep_session_id}/readiness",
    response_model=InterviewPrepReadinessRead,
)
async def get_interview_prep_readiness(
    prep_session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> InterviewPrepReadinessRead:
    service = InterviewPrepService()
    prep_session = await service.get_session(
        session,
        prep_session_id=prep_session_id,
        user_id=current_user.id,
    )
    return InterviewPrepReadinessRead.model_validate(prep_session.readiness_json or {})


def _to_read_model(prep_session) -> InterviewPrepSessionRead:
    readiness_json = prep_session.readiness_json or {}
    return InterviewPrepSessionRead(
        id=prep_session.id,
        application_id=prep_session.application_id,
        vacancy_id=prep_session.vacancy_id,
        prep_status=prep_session.prep_status,
        readiness_score=prep_session.readiness_score,
        competency_map=prep_session.competency_map_json or {},
        questions=prep_session.question_set_json or [],
        evidence_links=prep_session.evidence_links_json or [],
        weak_areas=prep_session.weak_areas_json or [],
        readiness=InterviewPrepReadinessRead.model_validate(readiness_json),
        provenance=dict(readiness_json.get("provenance") or {}),
        created_at=prep_session.created_at,
        updated_at=prep_session.updated_at,
    )
