# app\api\routes\applications.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.application import (
    ApplicationAnalyticsSummaryResponse,
    ApplicationCreateRequest,
    ApplicationDashboardItem,
    ApplicationEventItem,
    ApplicationDetailResponse,
    ApplicationReminderItem,
    ApplicationWorkflowResponse,
    ApplicationStatusHistoryItem,
    ApplicationSubmitRequest,
    ApplicationStatusUpdateRequest,
)
from app.services.application_analytics_service import ApplicationAnalyticsService
from app.services.application_reminder_service import ApplicationReminderService
from app.services.application_tracking_service import ApplicationTrackingService


router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationDetailResponse)
async def create_application(
    payload: ApplicationCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationDetailResponse:
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
        return ApplicationDetailResponse.model_validate(application)
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/analytics/summary",
    response_model=ApplicationAnalyticsSummaryResponse,
)
async def get_application_analytics_summary(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationAnalyticsSummaryResponse:
    service = ApplicationAnalyticsService()
    summary = await service.get_summary(
        session,
        user_id=current_user.id,
    )
    return ApplicationAnalyticsSummaryResponse.model_validate(summary)


@router.get(
    "/reminders",
    response_model=list[ApplicationReminderItem],
)
async def get_application_reminders(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApplicationReminderItem]:
    service = ApplicationReminderService()
    reminders = await service.get_reminders(
        session,
        user_id=current_user.id,
    )
    return [ApplicationReminderItem.model_validate(reminder) for reminder in reminders]


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationDetailResponse:
    service = ApplicationTrackingService()
    application = await service.get_application(
        session,
        application_id=application_id,
        user_id=current_user.id,
    )
    return ApplicationDetailResponse.model_validate(application)


@router.get(
    "/{application_id}/workflow",
    response_model=ApplicationWorkflowResponse,
)
async def get_application_workflow(
    application_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationWorkflowResponse:
    service = ApplicationTrackingService()
    application = await service.get_application(
        session,
        application_id=application_id,
        user_id=current_user.id,
    )
    workflow = service.get_application_workflow_metadata(application)
    return ApplicationWorkflowResponse.model_validate(workflow)


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


@router.patch("/{application_id}/status", response_model=ApplicationDetailResponse)
async def update_application_status(
    application_id: UUID,
    payload: ApplicationStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationDetailResponse:
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
        return ApplicationDetailResponse.model_validate(application)
    except Exception:
        await session.rollback()
        raise


@router.post("/{application_id}/submit", response_model=ApplicationDetailResponse)
async def submit_application(
    application_id: UUID,
    payload: ApplicationSubmitRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationDetailResponse:
    service = ApplicationTrackingService()
    try:
        application = await service.submit_application(
            session,
            application_id=application_id,
            user_id=current_user.id,
            source=payload.source,
            external_link=payload.external_link,
        )
        await session.commit()
        return ApplicationDetailResponse.model_validate(application)
    except Exception:
        await session.rollback()
        raise


@router.get("", response_model=list[ApplicationDashboardItem])
async def list_applications(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApplicationDashboardItem]:
    service = ApplicationTrackingService()
    items = await service.list_application_dashboard_items(
        session,
        user_id=current_user.id,
    )
    return [ApplicationDashboardItem(**item) for item in items]
