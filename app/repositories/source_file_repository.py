# app\repositories\source_file_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
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
        content_sha256: str | None = None,
        lifecycle_status: str = "active",
        lineage_group_id: UUID | None = None,
        superseded_by_id: UUID | None = None,
    ) -> SourceFile:
        source_file = SourceFile(
            user_id=user_id,
            file_kind=file_kind,
            storage_key=storage_key,
            original_name=original_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_sha256=content_sha256,
            lifecycle_status=lifecycle_status,
            lineage_group_id=lineage_group_id,
            superseded_by_id=superseded_by_id,
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
        user_id: UUID,
    ) -> SourceFile | None:
        stmt = select(SourceFile).where(SourceFile.id == file_id)
        result = await session.execute(stmt)
        source_file = result.scalar_one_or_none()
        if source_file is None:
            return None
        if source_file.user_id != user_id:
            return None
        return source_file

    async def list_by_user_and_kind(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        file_kind: str,
        include_superseded: bool = True,
    ) -> list[SourceFile]:
        """Список SourceFile пользователя по file_kind, свежие сверху.

        Сортировка updated_at desc → created_at desc (детерминированный
        tie-breaker для двух событий в один timestamp). Используется для
        ``GET /profile/resumes``, чтобы UI мог показать «историю загрузок».
        """
        stmt = (
            select(SourceFile)
            .where(
                SourceFile.user_id == user_id,
                SourceFile.file_kind == file_kind,
            )
            .order_by(SourceFile.updated_at.desc(), SourceFile.created_at.desc())
        )
        if not include_superseded:
            stmt = stmt.where(SourceFile.lifecycle_status == "active")
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_duplicate_by_hash(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        file_kind: str,
        content_sha256: str,
    ) -> SourceFile | None:
        stmt = (
            select(SourceFile)
            .where(
                SourceFile.user_id == user_id,
                SourceFile.file_kind == file_kind,
                SourceFile.content_sha256 == content_sha256,
            )
            .order_by(SourceFile.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_kind(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        file_kind: str,
    ) -> SourceFile | None:
        stmt = (
            select(SourceFile)
            .where(
                SourceFile.user_id == user_id,
                SourceFile.file_kind == file_kind,
                SourceFile.lifecycle_status == "active",
            )
            .order_by(SourceFile.updated_at.desc(), SourceFile.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def supersede_active_by_kind(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        file_kind: str,
        superseded_by_id: UUID,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = (
            update(SourceFile)
            .where(
                SourceFile.user_id == user_id,
                SourceFile.file_kind == file_kind,
                SourceFile.lifecycle_status == "active",
            )
            .values(
                lifecycle_status="superseded",
                superseded_by_id=superseded_by_id,
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(SourceFile.id != exclude_id)
        await session.execute(stmt)

    async def activate(
        self,
        session: AsyncSession,
        *,
        source_file: SourceFile,
    ) -> SourceFile:
        source_file.lifecycle_status = "active"
        source_file.superseded_by_id = None
        await session.flush()
        await session.refresh(source_file)
        return source_file
