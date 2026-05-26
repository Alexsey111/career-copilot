# app\services\application_tracking_service.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.application_models import (
    is_valid_transition,
    get_allowed_transitions,
)
from app.domain.application_events import (
    ApplicationEventType,
    normalize_application_event_type,
)
from app.domain.application_event_meta import (
    build_application_applied_meta,
    build_application_created_meta,
    build_application_status_changed_meta,
)
from app.repositories.application_event_repository import ApplicationEventRepository
from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.application_status_history_repository import (
    ApplicationStatusHistoryRepository,
)
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.application_safety_service import ApplicationSafetyService

APPLICATION_USER_VACANCY_UNIQUE_CONSTRAINT = "uq_application_records_user_vacancy"
APPLICATION_STATUS_LABELS: dict[str, str] = {
    "draft": "Черновик",
    "ready": "Готов к отправке",
    "applied": "Отправлен вручную",
    "screening": "Скрининг",
    "interview": "Интервью",
    "offer": "Оффер",
    "rejected": "Отказ",
    "withdrawn": "Отозван",
}
APPLICATION_WORKFLOW_ORDER: tuple[str, ...] = (
    "ready",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
    "draft",
)


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
        application_safety_service: ApplicationSafetyService | None = None,
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
        self.application_safety_service = (
            application_safety_service or ApplicationSafetyService()
        )

    def _workflow_status_label(self, status: str) -> str:
        normalized_status = status.strip().lower()
        return APPLICATION_STATUS_LABELS.get(normalized_status, normalized_status)

    def _sorted_allowed_transitions(self, current_status: str) -> list[str]:
        allowed = get_allowed_transitions(current_status) or set()
        return sorted(
            allowed,
            key=lambda value: (
                APPLICATION_WORKFLOW_ORDER.index(value)
                if value in APPLICATION_WORKFLOW_ORDER
                else len(APPLICATION_WORKFLOW_ORDER)
            ),
        )

    def get_application_workflow_metadata(self, application: Any) -> dict[str, Any]:
        current_status = str(getattr(application, "status", "") or "").strip().lower()
        allowed_transitions = self._sorted_allowed_transitions(current_status)
        review_state = self._get_application_review_state(application)

        return {
            "current_status": current_status,
            "allowed_transitions": [
                {
                    "status": status_value,
                    "label": self._workflow_status_label(status_value),
                }
                for status_value in allowed_transitions
            ],
            "can_submit": current_status == "ready",
            "is_final": len(allowed_transitions) == 0,
            **review_state,
        }

    def _event_type_for_status(self, status: str) -> ApplicationEventType:
        normalized_status = status.strip().lower()
        if normalized_status == "ready":
            return ApplicationEventType.APPLICATION_READY
        if normalized_status == "applied":
            return ApplicationEventType.APPLICATION_APPLIED
        if normalized_status in {"rejected", "offer", "withdrawn"}:
            return ApplicationEventType.OUTCOME_RECORDED
        return ApplicationEventType.APPLICATION_STATUS_CHANGED

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

        # Проверяем, что документы существуют и пригодны как snapshot versions.
        # Human review no longer blocks MVP application creation; it becomes a risk flag.
        if resume_document_id is not None:
            await self._validate_application_document(
                session,
                document_id=resume_document_id,
                user_id=user_id,
                vacancy_id=vacancy_id,
                expected_kind="resume",
                required=True,
            )

        if cover_letter_document_id is not None:
            await self._validate_application_document(
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
            await self._create_application_event(
                session,
                application_id=application.id,
                event_type=ApplicationEventType.APPLICATION_CREATED,
                title="Application created",
                description="Application record created in draft status",
                meta_json=build_application_created_meta(
                    vacancy_id=vacancy_id,
                    resume_document_id=resume_document_id,
                    cover_letter_document_id=cover_letter_document_id,
                ),
            )
            review_state = await self._annotate_application_review_state(
                session,
                application,
            )
            if review_state["review_required"]:
                await self._create_application_review_required_event(
                    session,
                    application_id=application.id,
                    review_state=review_state,
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
        await self._annotate_application_review_state(session, application)
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
            await self._validate_application_document(
                session,
                document_id=resume_document_id,
                user_id=user_id,
                vacancy_id=application.vacancy_id,
                expected_kind="resume",
                required=True,
            )

        if cover_letter_document_id is not None:
            await self._validate_application_document(
                session,
                document_id=cover_letter_document_id,
                user_id=user_id,
                vacancy_id=application.vacancy_id,
                expected_kind="cover_letter",
                required=False,
            )

        application.resume_document_id = resume_document_id
        application.cover_letter_document_id = cover_letter_document_id

        await self._create_application_event(
            session,
            application_id=application.id,
            event_type=ApplicationEventType.DOCUMENT_ATTACHED,
            title="Documents attached",
            description=(
                f"Resume: {resume_document_id}, "
                f"Cover Letter: {cover_letter_document_id}"
            ),
        )

        await session.flush()
        await session.refresh(application)
        review_state = await self._annotate_application_review_state(session, application)
        if review_state["review_required"]:
            await self._create_application_review_required_event(
                session,
                application_id=application.id,
                review_state=review_state,
            )
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

        await self._create_application_event(
            session,
            application_id=application.id,
            event_type=ApplicationEventType.INTERVIEW_SESSION_CREATED,
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

        await self._create_application_event(
            session,
            application_id=application.id,
            event_type=ApplicationEventType.NOTE_ADDED,
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

        await self._create_application_event(
            session,
            application_id=application.id,
            event_type=ApplicationEventType.EXTERNAL_LINK_ADDED,
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

        safety = await self.application_safety_service.can_apply(
            session,
            user_id=user_id,
            vacancy_id=application.vacancy_id,
        )

        review_required = not safety.allowed
        review_state = {
            "review_required": review_required,
            "review_blockers": [],
            "review_warnings": list(safety.blockers) + list(safety.warnings),
            "review_score": safety.score,
            "review_document_id": str(safety.document_id) if safety.document_id else None,
        }

        submission_source = source or "manual"
        application.status = "applied"
        application.source = submission_source
        application.external_link = external_link
        application.applied_at = datetime.now(timezone.utc)

        await self.application_status_history_repository.create(
            session,
            application_id=application.id,
            previous_status="ready",
            new_status="applied",
            notes=None,
        )

        await self._create_application_event(
            session,
            application_id=application.id,
            event_type=ApplicationEventType.APPLICATION_APPLIED,
            title="Application submitted manually",
            description="User confirmed manual submission",
            meta_json=build_application_applied_meta(
                source=submission_source,
                external_link=external_link,
                applied_at=application.applied_at,
            )
            | {
                "review_required": review_required,
                "review_blockers": [],
                "review_warnings": list(safety.blockers) + list(safety.warnings),
                "review_document_id": (
                    str(safety.document_id) if safety.document_id else None
                ),
                "review_score": safety.score,
            },
        )
        if review_required:
            await self._create_application_review_required_event(
                session,
                application_id=application.id,
                review_state=review_state,
            )

        await session.flush()
        await session.refresh(application)
        self._set_application_review_state(application, review_state)
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

        if normalized_status == "applied":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="use POST /applications/{application_id}/submit to submit applications",
            )

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

        await self._create_application_event(
            session,
            application_id=application.id,
            event_type=self._event_type_for_status(normalized_status),
            title=f"Status changed to {normalized_status}",
            description=notes,
            meta_json=build_application_status_changed_meta(
                previous_status=previous_status,
                new_status=normalized_status,
                source="manual",
            ),
        )

        await session.flush()
        await session.refresh(application)
        await self._annotate_application_review_state(session, application)
        return application

    def _validate_status_transition(
        self,
        *,
        current_status: str,
        next_status: str,
    ) -> None:
        """Deprecated: Use is_valid_transition from app.domain.application_models."""
        from app.domain.application_models import is_valid_transition

        if is_valid_transition(current_status, next_status):  # type: ignore
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid application status transition: {current_status} -> {next_status}",
        )

    async def _create_application_event(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        event_type: str | ApplicationEventType,
        title: str | None = None,
        description: str | None = None,
        meta_json: dict | None = None,
    ) -> None:
        """Создаёт запись события в timeline приложения."""
        normalized_event_type = normalize_application_event_type(event_type)
        event_type_value = (
            normalized_event_type.value if normalized_event_type is not None else str(event_type)
        )
        await self.application_event_repository.create(
            session,
            application_id=application_id,
            event_type=event_type_value,
            title=title,
            description=description,
            meta_json=meta_json,
        )

    async def _add_event(
        self,
        session: AsyncSession,
        *,
        application: Any,
        event_type: str | ApplicationEventType,
        title: str | None = None,
        description: str | None = None,
        meta_json: dict | None = None,
    ) -> None:
        """Deprecated: use _create_application_event."""
        await self._create_application_event(
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
        await self._annotate_application_review_state(session, application)
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
            await self._annotate_application_review_state(session, application)
            vacancy = application.vacancy
            review_state = self._get_application_review_state(application)

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
                    **review_state,
                    "created_at": application.created_at,
                    "updated_at": application.updated_at,
                }
            )

        return items

    async def _annotate_application_review_state(
        self,
        session: AsyncSession,
        application: Any,
    ) -> dict[str, Any]:
        review_state = await self._calculate_application_review_state(
            session,
            application=application,
        )
        self._set_application_review_state(application, review_state)
        return review_state

    async def _calculate_application_review_state(
        self,
        session: AsyncSession,
        *,
        application: Any,
    ) -> dict[str, Any]:
        blockers: list[str] = []
        warnings: list[str] = []

        for document_id, expected_kind, required in (
            (application.resume_document_id, "resume", True),
            (application.cover_letter_document_id, "cover_letter", False),
        ):
            if document_id is None:
                continue

            document = await self.document_version_repository.get_by_id(
                session,
                document_id,
                user_id=application.user_id,
            )
            if document is None:
                if required:
                    blockers.append(f"{expected_kind} document not found")
                continue

            if document.document_kind != expected_kind:
                blockers.append(f"document must be {expected_kind}")
                continue

            if document.rendered_text is None and required:
                blockers.append(f"{expected_kind} document has no rendered text")

            if document.review_status != "approved":
                warnings.append(f"{expected_kind} document review is not approved")

            content = document.content_json or {}
            sections = content.get("sections", {})
            unresolved_claims = sections.get("claims_needing_confirmation", [])
            if unresolved_claims:
                warnings.append(
                    f"{expected_kind} document has unresolved claims requiring confirmation"
                )

        review_required = bool(blockers or warnings)
        return {
            "review_required": review_required,
            "review_blockers": blockers,
            "review_warnings": warnings,
        }

    def _set_application_review_state(
        self,
        application: Any,
        review_state: dict[str, Any],
    ) -> None:
        application.review_required = bool(review_state.get("review_required"))
        application.review_blockers = list(review_state.get("review_blockers") or [])
        application.review_warnings = list(review_state.get("review_warnings") or [])

    def _get_application_review_state(self, application: Any) -> dict[str, Any]:
        return {
            "review_required": bool(getattr(application, "review_required", False)),
            "review_blockers": list(getattr(application, "review_blockers", []) or []),
            "review_warnings": list(getattr(application, "review_warnings", []) or []),
        }

    async def _create_application_review_required_event(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        review_state: dict[str, Any],
    ) -> None:
        await self._create_application_event(
            session,
            application_id=application_id,
            event_type=ApplicationEventType.APPLICATION_REVIEW_REQUIRED,
            title="Application requires review",
            description="Application flow continued with review-required risk flags",
            meta_json={
                "review_required": bool(review_state.get("review_required")),
                "review_blockers": list(review_state.get("review_blockers") or []),
                "review_warnings": list(review_state.get("review_warnings") or []),
                "review_document_id": review_state.get("review_document_id"),
                "review_score": review_state.get("review_score"),
            },
        )
