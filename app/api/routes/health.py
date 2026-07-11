"""Health and diagnostics routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.demo_scenarios import get_demo_scenarios
from app.db.session import get_db_session
from app.models import ApplicationRecord, DocumentVersion, InterviewPrepSession, Vacancy, User
from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.schemas.health import (
    HealthApplicationSummary,
    HealthCountsResponse,
    HealthDiagnosticsResponse,
    HealthDocumentSummary,
)
from app.security.dependencies import get_current_active_user

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/storage")
async def storage_healthcheck() -> dict[str, str | bool]:
    from app.services.storage_service import StorageService

    try:
        ok = StorageService().healthcheck()
    except Exception:
        ok = False
    return {"status": "ok" if ok else "degraded", "storage_ok": bool(ok)}


@router.get("/health/db-info")
async def db_info() -> dict[str, str | int | None]:
    settings = get_settings()

    if settings.app_env not in {"local", "test"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    url = make_url(settings.database_url)

    return {
        "environment": settings.app_env,
        "db_driver": url.drivername,
        "db_host": url.host,
        "db_port": url.port,
        "db_name": url.database,
    }


@router.get("/health/diagnostics", response_model=HealthDiagnosticsResponse)
async def health_diagnostics(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> HealthDiagnosticsResponse:
    application_repo = ApplicationRecordRepository()
    document_repo = DocumentVersionRepository()

    counts_query = {
        "vacancies": select(func.count()).select_from(Vacancy).where(Vacancy.user_id == current_user.id),
        "applications": select(func.count()).select_from(ApplicationRecord).where(
            ApplicationRecord.user_id == current_user.id
        ),
        "documents": select(func.count()).select_from(DocumentVersion).where(
            DocumentVersion.user_id == current_user.id
        ),
        "interview_sessions": select(func.count()).select_from(InterviewPrepSession).where(
            InterviewPrepSession.user_id == current_user.id
        ),
    }

    counts_values: dict[str, int] = {}
    for key, stmt in counts_query.items():
        result = await session.execute(stmt)
        counts_values[key] = int(result.scalar_one() or 0)

    applications = await application_repo.list_by_user_id(session, current_user.id)

    active_statuses = {"draft", "ready", "applied", "screening", "interview"}
    current_application = next(
        (
            application
            for application in applications
            if application.resume_document_id
            and application.cover_letter_document_id
            and application.status in active_statuses
        ),
        None,
    )
    if current_application is None:
        current_application = next(
            (
                application
                for application in applications
                if application.resume_document_id and application.cover_letter_document_id
            ),
            applications[0] if applications else None,
        )
    current_active_application = None
    active_documents: dict[str, HealthDocumentSummary | None] = {}
    if current_application is not None:
        current_active_application = HealthApplicationSummary(
            id=current_application.id,
            vacancy_id=current_application.vacancy_id,
            status=current_application.status,
            source=current_application.source,
            resume_document_id=current_application.resume_document_id,
            cover_letter_document_id=current_application.cover_letter_document_id,
            created_at=current_application.created_at,
            updated_at=current_application.updated_at,
        )

        resume_document = await document_repo.get_active_for_scope(
            session,
            user_id=current_user.id,
            vacancy_id=current_application.vacancy_id,
            document_kind="resume",
        )
        cover_letter_document = await document_repo.get_active_for_scope(
            session,
            user_id=current_user.id,
            vacancy_id=current_application.vacancy_id,
            document_kind="cover_letter",
        )

        def _to_document_summary(document: DocumentVersion | None) -> HealthDocumentSummary | None:
            if document is None:
                return None
            return HealthDocumentSummary(
                id=document.id,
                vacancy_id=document.vacancy_id,
                document_kind=document.document_kind,
                version_label=document.version_label,
                review_status=document.review_status,
                is_active=document.is_active,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )

        active_documents = {
            "resume": _to_document_summary(resume_document),
            "cover_letter": _to_document_summary(cover_letter_document),
        }

    has_documents = counts_values["documents"] > 0
    has_active_documents = any(active_documents.values())
    has_interview_sessions = counts_values["interview_sessions"] > 0
    has_applications = counts_values["applications"] > 0
    has_vacancies = counts_values["vacancies"] > 0

    demo_state = {
        "has_demo_data": has_vacancies or has_applications or has_documents or has_interview_sessions,
        "has_vacancies": has_vacancies,
        "has_applications": has_applications,
        "has_documents": has_documents,
        "has_active_documents": has_active_documents,
        "has_interview_sessions": has_interview_sessions,
        "current_active_application_id": (
            str(current_active_application.id) if current_active_application is not None else None
        ),
        "current_active_vacancy_id": (
            str(current_active_application.vacancy_id) if current_active_application is not None else None
        ),
    }

    return HealthDiagnosticsResponse(
        current_user_id=current_user.id,
        counts=HealthCountsResponse(**counts_values),
        current_active_application=current_active_application,
        active_documents=active_documents,
        demo_state=demo_state,
        scenario_identifiers=get_demo_scenarios(),
    )
