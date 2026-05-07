# app\services\document_diff_service.py

from __future__ import annotations

import difflib
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import (
    DocumentVersionRepository,
)


class DocumentDiffService:
    def __init__(
        self,
        document_version_repository: (
            DocumentVersionRepository | None
        ) = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository
            or DocumentVersionRepository()
        )

    async def build_diff(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        document_id: UUID,
        other_document_id: UUID,
    ) -> dict:
        left = await self.document_version_repository.get_by_id(
            session,
            document_id,
            user_id=user_id,
        )

        if left is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )

        right = await self.document_version_repository.get_by_id(
            session,
            other_document_id,
            user_id=user_id,
        )

        if right is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="other document not found",
            )

        if left.document_kind != right.document_kind:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="documents must have same document_kind",
            )

        left_text = left.rendered_text or ""
        right_text = right.rendered_text or ""

        diff = difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=str(left.id),
            tofile=str(right.id),
            lineterm="",
        )

        return {
            "document_id": left.id,
            "other_document_id": right.id,
            "document_kind": left.document_kind,
            "diff": "\n".join(diff),
        }