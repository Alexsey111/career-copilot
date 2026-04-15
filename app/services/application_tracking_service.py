# app\services\application_tracking_service.py

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.vacancy_repository import VacancyRepository


ALLOWED_APPLICATION_STATUSES = {
    "draft",
    "submitted",
    "interview",
    "rejected",
    "offer",
}


class ApplicationTrackingService:
    def __init__(
        self,
        application_record_repository: ApplicationRecordRepository | None = None,
        vacancy_repository: VacancyRepository | None = None,
        document_version_repository: DocumentVersionRepository | None = None,
    ) -> None:
        self.application_record_repository = (
            application_record_repository or ApplicationRecordRepository()
        )
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )

    async def create_application(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        resume_document_id: UUID | None,
        cover_letter_document_id: UUID | None,
        notes: str | None,
    ):
        vacancy = await self.vacancy_repository.get_by_id(session, vacancy_id)
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        if vacancy.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        existing = await self.application_record_repository.get_by_user_id_and_vacancy_id(
            session,
            user_id=user_id,
            vacancy_id=vacancy_id,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="application already exists for this vacancy",
            )

        selected_resume_id = resume_document_id
        if selected_resume_id is None:
            active_resume = await self.document_version_repository.get_active_for_scope(
                session,
                user_id=vacancy.user_id,
                vacancy_id=vacancy.id,
                document_kind="resume",
            )
            if active_resume is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="no active resume found for this vacancy",
                )
            selected_resume_id = active_resume.id

        selected_cover_letter_id = cover_letter_document_id
        if selected_cover_letter_id is None:
            active_cover_letter = await self.document_version_repository.get_active_for_scope(
                session,
                user_id=vacancy.user_id,
                vacancy_id=vacancy.id,
                document_kind="cover_letter",
            )
            if active_cover_letter is not None:
                selected_cover_letter_id = active_cover_letter.id

        await self.application_record_repository.create(
            session,
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            resume_document_id=selected_resume_id,
            cover_letter_document_id=selected_cover_letter_id,
            status="draft",
            channel="manual",
            applied_at=None,
            outcome=None,
            notes=notes,
        )

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="application already exists for this vacancy",
            ) from exc

        application = await self.application_record_repository.get_by_user_id_and_vacancy_id(
            session,
            user_id=user_id,
            vacancy_id=vacancy_id,
        )
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="application was not found after commit",
            )

        return application

    async def update_status(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        status_value: str,
        notes: str | None,
    ):
        application = await self.application_record_repository.get_by_id(session, application_id)
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="application not found",
            )

        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="application not found",
            )

        normalized_status = status_value.strip().lower()
        if normalized_status not in ALLOWED_APPLICATION_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status must be one of: {sorted(ALLOWED_APPLICATION_STATUSES)}",
            )

        application.status = normalized_status

        if notes:
            application.notes = notes

        if normalized_status == "submitted" and application.applied_at is None:
            application.applied_at = datetime.now(timezone.utc)

        if normalized_status == "rejected":
            application.outcome = "rejected"

        if normalized_status == "offer":
            application.outcome = "offer"

        await session.commit()
        await session.refresh(application)
        return application

    async def get_application(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
    ):
        application = await self.application_record_repository.get_by_id(session, application_id)
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="application not found",
            )
        if application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="application not found",
            )
        return application

    async def list_applications(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ):
        return await self.application_record_repository.list_by_user_id(session, user_id)
