# app\api\routes\evidence.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, require_data_processing_consent
from app.db.session import get_db_session
from app.models import User
from app.schemas.case_prep import CasePrepReportResponse
from app.schemas.interview_prep import (
    InterviewPrepReadinessRead,
    InterviewPrepSessionDeleteRequest,
    InterviewPrepSessionCreateRequest,
    InterviewPrepSessionListItem,
    InterviewPrepSessionRead,
)
from app.services.case_prep_service import CasePrepService
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


@router.delete("/sessions")
async def delete_interview_prep_sessions(
    application_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    service = InterviewPrepService()
    deleted_count = await service.delete_sessions(
        session,
        user_id=current_user.id,
        application_id=application_id,
    )
    return {"deleted_count": deleted_count}


@router.post("/sessions/delete")
async def delete_interview_prep_sessions_by_ids(
    payload: InterviewPrepSessionDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    service = InterviewPrepService()
    deleted_count = await service.delete_sessions_by_ids(
        session,
        user_id=current_user.id,
        session_ids=list(payload.session_ids or []),
    )
    return {"deleted_count": deleted_count}


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


@router.get("/cases/{vacancy_id}", response_model=CasePrepReportResponse)
async def get_interview_prep_cases(
    vacancy_id: UUID,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> CasePrepReportResponse:
    """Этап 9.E: детерминированный on-demand practice-кейсы по вакансии.

    Без AI, без миграции БД, без персистентности. Кейсы — шаблонные сценарии
    (system_design/debugging_scenario/data_analysis/behavioral_case/take_home_brief)
    с rubric, структурой ответа и recommended_evidence из подтверждённого STAR.
    ``requires_human_review`` всегда True. См. ``docs/interview_prep_contract.md``.
    """
    service = CasePrepService()
    report = await service.build_case_set(
        session,
        user_id=current_user.id,
        vacancy_id=vacancy_id,
    )
    return CasePrepReportResponse.model_validate(report)


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
