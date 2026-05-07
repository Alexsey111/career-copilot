# app\services\document_review_service.py

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import DocumentVersionRepository
from app.services.document_activation_service import (
    DocumentActivationService,
)


ALLOWED_REVIEW_STATUSES = {"draft", "approved", "rejected", "needs_edit"}


class DocumentReviewService:
    def __init__(
        self,
        document_version_repository: DocumentVersionRepository | None = None,
        document_activation_service: DocumentActivationService | None = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository
            or DocumentVersionRepository()
        )

        self.document_activation_service = (
            document_activation_service
            or DocumentActivationService(
                document_version_repository=self.document_version_repository,
            )
        )

    async def review_document(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        user_id: UUID,
        review_status: str,
        review_comment: str | None,
        set_active_when_approved: bool,
    ):
        normalized_status = review_status.strip().lower()
        if normalized_status not in ALLOWED_REVIEW_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"review_status must be one of: {sorted(ALLOWED_REVIEW_STATUSES)}",
            )

        document = await self.document_version_repository.get_by_id(
            session,
            document_id,
            user_id=user_id,
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )

        content_json = dict(document.content_json or {})
        review_section = dict(content_json.get("review", {}))
        review_history = list(review_section.get("history", []))

        review_event = {
            "status": normalized_status,
            "comment": review_comment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        review_history.append(review_event)

        review_section["latest_status"] = normalized_status
        review_section["latest_comment"] = review_comment
        review_section["history"] = review_history
        content_json["review"] = review_section

        document.review_status = normalized_status
        document.content_json = content_json

        if normalized_status == "approved" and set_active_when_approved:
            await session.commit()

            document = await self.document_activation_service.activate_document(
                session,
                document_id=document.id,
                user_id=user_id,
            )

        elif normalized_status in {"rejected", "needs_edit"}:
            document.is_active = False

        await session.commit()
        await session.refresh(document)
        return document
