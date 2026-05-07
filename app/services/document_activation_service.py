# app\services\document_activation_service.py

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import (
    DocumentVersionRepository,
)


class DocumentActivationService:
    def __init__(
        self,
        document_version_repository: DocumentVersionRepository | None = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )

    async def activate_document(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        user_id: UUID,
    ):
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

        if document.review_status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="only approved documents can be activated",
            )

        await self.document_version_repository.deactivate_same_scope(
            session,
            user_id=document.user_id,
            vacancy_id=document.vacancy_id,
            document_kind=document.document_kind,
            exclude_document_id=document.id,
        )

        content_json = dict(document.content_json or {})

        activation_section = dict(
            content_json.get("activation", {})
        )
        history = list(
            activation_section.get("history", [])
        )

        activation_event = {
            "event": "activated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        history.append(activation_event)

        activation_section["history"] = history
        activation_section["last_activated_at"] = (
            activation_event["timestamp"]
        )

        content_json["activation"] = activation_section

        document.content_json = content_json
        document.is_active = True

        await session.commit()
        await session.refresh(document)

        return document