# app\api\routes\applications.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationEventItem,
    ApplicationListItem,
    ApplicationRead,
    ApplicationStatusHistoryItem,
    ApplicationStatusUpdateRequest,
)
from app.services.application_tracking_service import ApplicationTrackingService


router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationRead)
async def create_application(
    payload: ApplicationCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationRead:
    service = ApplicationTrackingService()
    try:
        application = await service.create_application(
            session,
            user_id=current_user.id,
            vacancy_id=payload.vacancy_id,
            resume_document_id=payload.resume_document_id,
            cover_letter_document_id=payload.cover_letter_document_id,
            source=payload.source,
            notes=payload.notes,
        )
        await session.commit()
        return ApplicationRead.model_validate(application)
    except Exception:
        await session.rollback()
        raise


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationRead:
    service = ApplicationTrackingService()
    application = await service.get_application(
        session,
        application_id=application_id,
        user_id=current_user.id,
    )
    return ApplicationRead.model_validate(application)


@router.get(
    "/{application_id}/timeline",
    response_model=list[ApplicationStatusHistoryItem],
)
async def get_application_timeline(
    application_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApplicationStatusHistoryItem]:
    service = ApplicationTrackingService()
    timeline = await service.get_application_status_history(
        session,
        application_id=application_id,
        user_id=current_user.id,
    )
    return [ApplicationStatusHistoryItem.model_validate(item) for item in timeline]


@router.get(
    "/{application_id}/activity-log",
    response_model=list[ApplicationEventItem],
)
async def get_application_activity_log(
    application_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApplicationEventItem]:
    service = ApplicationTrackingService()
    log = await service.get_application_timeline(
        session,
        application_id=application_id,
        user_id=current_user.id,
    )
    return [ApplicationEventItem.model_validate(item) for item in log]


@router.patch("/{application_id}/status", response_model=ApplicationRead)
async def update_application_status(
    application_id: UUID,
    payload: ApplicationStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationRead:
    service = ApplicationTrackingService()
    try:
        application = await service.update_status(
            session,
            application_id=application_id,
            user_id=current_user.id,
            status_value=payload.status,
            notes=payload.notes,
        )
        await session.commit()
        return ApplicationRead.model_validate(application)
    except Exception:
        await session.rollback()
        raise


@router.get("", response_model=list[ApplicationListItem])
async def list_applications(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApplicationListItem]:
    service = ApplicationTrackingService()
    items = await service.list_application_dashboard_items(
        session,
        user_id=current_user.id,
    )
    return [ApplicationListItem(**item) for item in items]
