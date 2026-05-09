# app\services\application_tracking_service.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.application_models import (
    ApplicationStatus,
    is_valid_transition,
    get_allowed_transitions,
)
from app.repositories.application_event_repository import ApplicationEventRepository
from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.application_status_history_repository import (
    ApplicationStatusHistoryRepository,
)
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.vacancy_repository import VacancyRepository

APPLICATION_USER_VACANCY_UNIQUE_CONSTRAINT = "uq_application_records_user_vacancy"


def _is_duplicate_application_error(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False

    constraint_name = getattr(orig, "constraint_name", None)
    if constraint_name == APPLICATION_USER_VACANCY_UNIQUE_CONSTRAINT:
        return True

    diag = getattr(orig, "diag", None)
    if diag is not None and getattr(diag, "constraint_name", None) == APPLICATION_USER_VACANCY_UNIQUE_CONSTRAINT:
        return True

    message = str(orig)
    return APPLICATION_USER_VACANCY_UNIQUE_CONSTRAINT in message


class ApplicationTrackingService:
    def __init__(
        self,
        application_record_repository: ApplicationRecordRepository | None = None,
        application_status_history_repository: (
            ApplicationStatusHistoryRepository | None
        ) = None,
        application_event_repository: ApplicationEventRepository | None = None,
        vacancy_repository: VacancyRepository | None = None,
        document_version_repository: DocumentVersionRepository | None = None,
    ) -> None:
        self.application_record_repository = (
            application_record_repository or ApplicationRecordRepository()
        )
        self.application_status_history_repository = (
            application_status_history_repository
            or ApplicationStatusHistoryRepository()
        )
        self.application_event_repository = (
            application_event_repository or ApplicationEventRepository()
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
        resume_document_id: UUID | None = None,
        cover_letter_document_id: UUID | None = None,
        source: str | None = None,
        notes: str | None = None,
    ):
        vacancy = await self.vacancy_repository.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        # Проверяем, что документы существуют и approved (snapshot versions)
        if resume_document_id is not None:
            resume_doc = await self._validate_application_document(
                session,
                document_id=resume_document_id,
                user_id=user_id,
                vacancy_id=vacancy_id,
                expected_kind="resume",
                required=True,
            )

        if cover_letter_document_id is not None:
            cover_letter_doc = await self._validate_application_document(
                session,
                document_id=cover_letter_document_id,
                user_id=user_id,
                vacancy_id=vacancy_id,
                expected_kind="cover_letter",
                required=False,
            )

        source = source or vacancy.source

        try:
            application = await self.application_record_repository.create(
                session,
                user_id=user_id,
                vacancy_id=vacancy_id,
                resume_document_id=resume_document_id,
                cover_letter_document_id=cover_letter_document_id,
                status="draft",
                source=source,
                notes=notes,
            )
            await self.application_status_history_repository.create(
                session,
                application_id=application.id,
                previous_status=None,
                new_status="draft",
                notes=notes,
            )
            await self._add_event(
                session,
                application=application,
                event_type="status_changed",
                title="Application created",
                description="Application record created in draft status",
            )
            await session.flush()
        except IntegrityError as exc:
            if _is_duplicate_application_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="application already exists for this vacancy",
                ) from exc
            raise

        await session.refresh(application)
        return application

    async def _validate_application_document(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        user_id: UUID,
        vacancy_id: UUID,
        expected_kind: str,
        required: bool,
    ):
        document = await self.document_version_repository.get_by_id(
            session,
            document_id,
            user_id=user_id,
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{expected_kind} document not found",
            )

        if document.document_kind != expected_kind:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"document must be {expected_kind}",
            )

        if document.vacancy_id != vacancy_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{expected_kind} document does not belong to this vacancy",
            )

        if required and document.rendered_text is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{expected_kind} document has no rendered text",
            )

        if document.review_status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{expected_kind} document must be approved before application",
            )

        return document

    async def attach_documents(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        resume_document_id: UUID | None = None,
        cover_letter_document_id: UUID | None = None,
    ):
        """Прикрепляет versioned документы к application."""
        application = await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )

        # Проверяем документы
        if resume_document_id is not None:
            resume_doc = await self._validate_application_document(
                session,
                document_id=resume_document_id,
                user_id=user_id,
                vacancy_id=application.vacancy_id,
                expected_kind="resume",
                required=True,
            )

        if cover_letter_document_id is not None:
            cover_letter_doc = await self._validate_application_document(
                session,
                document_id=cover_letter_document_id,
                user_id=user_id,
                vacancy_id=application.vacancy_id,
                expected_kind="cover_letter",
                required=False,
            )

        application.resume_document_id = resume_document_id
        application.cover_letter_document_id = cover_letter_document_id

        await self._add_event(
            session,
            application=application,
            event_type="document_attached",
            title="Documents attached",
            description=(
                f"Resume: {resume_document_id}, "
                f"Cover Letter: {cover_letter_document_id}"
            ),
        )

        await session.flush()
        await session.refresh(application)
        return application

    async def schedule_interview(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        interview_date: datetime,
        notes: str | None = None,
    ):
        """Запланировать интервью."""
        application = await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )

        await self._add_event(
            session,
            application=application,
            event_type="interview_scheduled",
            title="Interview scheduled",
            description=notes,
            meta_json={"interview_date": interview_date.isoformat()},
        )

        await session.flush()
        return application

    async def add_note(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        note: str,
    ):
        """Добавить заметку."""
        application = await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )

        await self._add_event(
            session,
            application=application,
            event_type="note_added",
            title="Note added",
            description=note,
        )

        await session.flush()
        return application

    async def add_external_link(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        external_link: str,
    ):
        """Добавить внешнюю ссылку."""
        application = await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )

        application.external_link = external_link

        await self._add_event(
            session,
            application=application,
            event_type="external_link_added",
            title="External link added",
            description=f"Link: {external_link}",
        )

        await session.flush()
        await session.refresh(application)
        return application

    async def submit_application(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        source: str | None = None,
        external_link: str | None = None,
    ):
        """Подаёт application (ready → applied)."""
        application = await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )

        if application.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"can only submit application with status 'ready', current: {application.status}",
            )

        if application.resume_document_id is None and application.cover_letter_document_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="at least one document must be attached before submission",
            )

        application.status = "applied"
        application.source = source
        application.external_link = external_link
        application.applied_at = datetime.now(timezone.utc)

        await self.application_status_history_repository.create(
            session,
            application_id=application.id,
            previous_status="ready",
            new_status="applied",
            notes=None,
        )

        await self._add_event(
            session,
            application=application,
            event_type="applied",
            title="Application submitted",
            description=f"Submitted via {source or 'manual'}",
        )

        await session.flush()
        await session.refresh(application)
        return application

    async def update_status(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
        status_value: str,
        notes: str | None = None,
    ):
        application = await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )

        normalized_status = status_value.strip().lower()

        if not is_valid_transition(application.status, normalized_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"invalid application status transition: {application.status} -> {normalized_status}"
                ),
            )

        previous_status = application.status
        application.status = normalized_status

        if notes:
            application.notes = notes

        if normalized_status == "applied" and application.applied_at is None:
            application.applied_at = datetime.now(timezone.utc)

        if normalized_status in {"rejected", "offer", "withdrawn"}:
            application.outcome = normalized_status

        await self.application_status_history_repository.create(
            session,
            application_id=application.id,
            previous_status=previous_status,
            new_status=normalized_status,
            notes=notes,
        )

        await self._add_event(
            session,
            application=application,
            event_type="status_changed",
            title=f"Status changed to {normalized_status}",
            description=notes,
        )

        await session.flush()
        await session.refresh(application)
        return application

    def _validate_status_transition(
        self,
        *,
        current_status: str,
        next_status: str,
    ) -> None:
        """Deprecated: Use is_valid_transition from app.domain.application_models."""
        from app.domain.application_models import is_valid_transition, get_allowed_transitions

        if is_valid_transition(current_status, next_status):  # type: ignore
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid application status transition: {current_status} -> {next_status}",
        )

    async def _add_event(
        self,
        session: AsyncSession,
        *,
        application: Any,
        event_type: str,
        title: str | None = None,
        description: str | None = None,
        meta_json: dict | None = None,
    ) -> None:
        """Добавляет событие в timeline."""
        await self.application_event_repository.create(
            session,
            application_id=application.id,
            event_type=event_type,
            title=title,
            description=description,
            meta_json=meta_json,
        )

    async def get_application(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
    ):
        application = await self.application_record_repository.get_by_id(
            session,
            application_id,
            user_id=user_id,
        )
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="application not found",
            )
        return application

    async def get_application_timeline(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
    ):
        await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )
        return await self.application_event_repository.list_by_application_id(
            session,
            application_id=application_id,
        )

    async def get_application_status_history(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        user_id: UUID,
    ):
        await self.get_application(
            session,
            application_id=application_id,
            user_id=user_id,
        )
        return await self.application_status_history_repository.list_by_application_id(
            session,
            application_id=application_id,
        )

    async def list_applications(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ):
        return await self.application_record_repository.list_by_user_id(session, user_id)

    async def list_application_dashboard_items(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        applications = await self.application_record_repository.list_by_user_id(
            session,
            user_id,
        )

        items: list[dict] = []

        for application in applications:
            vacancy = application.vacancy

            items.append(
                {
                    "id": application.id,
                    "vacancy_id": application.vacancy_id,
                    "vacancy_title": vacancy.title if vacancy else None,
                    "vacancy_company": vacancy.company if vacancy else None,
                    "vacancy_location": vacancy.location if vacancy else None,
                    "resume_document_id": application.resume_document_id,
                    "cover_letter_document_id": application.cover_letter_document_id,
                    "status": application.status,
                    "source": application.source,
                    "external_link": application.external_link,
                    "applied_at": application.applied_at,
                    "outcome": application.outcome,
                    "notes": application.notes,
                    "created_at": application.created_at,
                    "updated_at": application.updated_at,
                }
            )

        return items
