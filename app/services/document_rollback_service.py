# app\services\document_rollback_service.py

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import (
    DocumentVersionRepository,
)


class DocumentRollbackService:
    def __init__(
        self,
        document_version_repository: DocumentVersionRepository | None = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )

    async def rollback_document(
        self,
        session: AsyncSession,
        *,
        source_document_id: UUID,
        user_id: UUID,
    ):
        source_document = await self.document_version_repository.get_by_id(
            session,
            source_document_id,
            user_id=user_id,
        )

        if source_document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )

        await self.document_version_repository.deactivate_same_scope(
            session,
            user_id=source_document.user_id,
            vacancy_id=source_document.vacancy_id,
            document_kind=source_document.document_kind,
            exclude_document_id=source_document.id,
        )

        content_json = dict(source_document.content_json or {})

        review_section = dict(content_json.get("review", {}))

        rollback_event = {
            "event": "rollback",
            "source_document_id": str(source_document.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        rollback_history = list(
            review_section.get("rollback_history", [])
        )
        rollback_history.append(rollback_event)

        review_section["rollback_history"] = rollback_history
        content_json["review"] = review_section

        cloned_document = await self.document_version_repository.create(
            session,
            user_id=source_document.user_id,
            vacancy_id=source_document.vacancy_id,
            derived_from_id=source_document.id,
            analysis_id=source_document.analysis_id,
            document_kind=source_document.document_kind,
            version_label=f"{source_document.version_label}_rollback",
            review_status="approved",
            is_active=True,
            content_json=content_json,
            rendered_text=source_document.rendered_text,
        )

        await session.commit()
        await session.refresh(cloned_document)

        return cloned_document