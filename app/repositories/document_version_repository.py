# app\repositories\document_version_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentVersion


class DocumentVersionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID | None,
        derived_from_id: UUID | None,
        document_kind: str,
        version_label: str | None,
        review_status: str,
        is_active: bool,
        content_json: dict,
        rendered_text: str | None,
    ) -> DocumentVersion:
        document = DocumentVersion(
            user_id=user_id,
            vacancy_id=vacancy_id,
            derived_from_id=derived_from_id,
            document_kind=document_kind,
            version_label=version_label,
            review_status=review_status,
            is_active=is_active,
            content_json=content_json,
            rendered_text=rendered_text,
        )
        session.add(document)
        await session.flush()
        await session.refresh(document)
        return document

    async def get_by_id(
        self,
        session: AsyncSession,
        document_id: UUID,
        *,
        user_id: UUID,
    ) -> DocumentVersion | None:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.id == document_id)
            .where(DocumentVersion.user_id == user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_for_scope(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID | None,
        document_kind: str,
    ) -> DocumentVersion | None:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.user_id == user_id)
            .where(DocumentVersion.document_kind == document_kind)
            .where(DocumentVersion.is_active.is_(True))
        )

        if vacancy_id is None:
            stmt = stmt.where(DocumentVersion.vacancy_id.is_(None))
        else:
            stmt = stmt.where(DocumentVersion.vacancy_id == vacancy_id)

        stmt = stmt.order_by(DocumentVersion.updated_at.desc()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate_same_scope(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID | None,
        document_kind: str,
        exclude_document_id: UUID,
    ) -> None:
        stmt = (
            update(DocumentVersion)
            .where(DocumentVersion.user_id == user_id)
            .where(DocumentVersion.document_kind == document_kind)
            .where(DocumentVersion.id != exclude_document_id)
        )

        if vacancy_id is None:
            stmt = stmt.where(DocumentVersion.vacancy_id.is_(None))
        else:
            stmt = stmt.where(DocumentVersion.vacancy_id == vacancy_id)

        stmt = stmt.values(is_active=False)
        await session.execute(stmt)
