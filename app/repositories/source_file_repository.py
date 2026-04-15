# app\repositories\source_file_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceFile


class SourceFileRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        file_kind: str,
        storage_key: str,
        original_name: str,
        mime_type: str | None,
        size_bytes: int | None,
    ) -> SourceFile:
        source_file = SourceFile(
            user_id=user_id,
            file_kind=file_kind,
            storage_key=storage_key,
            original_name=original_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        session.add(source_file)
        await session.flush()
        await session.refresh(source_file)
        return source_file

    async def get_by_id(
        self,
        session: AsyncSession,
        file_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> SourceFile | None:
        stmt = select(SourceFile).where(SourceFile.id == file_id)
        if user_id is not None:
            stmt = stmt.where(SourceFile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
