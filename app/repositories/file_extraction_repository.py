# app\repositories\file_extraction_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FileExtraction, SourceFile


class FileExtractionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        source_file_id,
        status: str,
        parser_name: str,
        parser_version: str | None,
        extracted_text: str,
        extracted_metadata_json: dict,
    ) -> FileExtraction:
        extraction = FileExtraction(
            source_file_id=source_file_id,
            status=status,
            parser_name=parser_name,
            parser_version=parser_version,
            extracted_text=extracted_text,
            extracted_metadata_json=extracted_metadata_json,
        )
        session.add(extraction)
        await session.flush()
        await session.refresh(extraction)
        return extraction

    async def get_by_id(
        self,
        session: AsyncSession,
        extraction_id: UUID,
        *,
        user_id: UUID,
    ) -> FileExtraction | None:
        stmt = (
            select(FileExtraction)
            .options(selectinload(FileExtraction.source_file))
            .where(FileExtraction.id == extraction_id)
        )
        result = await session.execute(stmt)
        extraction = result.scalar_one_or_none()
        if extraction is None:
            return None
        if extraction.source_file is not None and extraction.source_file.user_id != user_id:
            return None
        return extraction

    async def get_latest_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> FileExtraction | None:
        stmt = (
            select(FileExtraction)
            .join(SourceFile, SourceFile.id == FileExtraction.source_file_id)
            .options(selectinload(FileExtraction.source_file))
            .where(SourceFile.user_id == user_id)
            .order_by(FileExtraction.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_active_source_file_kind(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        file_kind: str,
    ) -> FileExtraction | None:
        stmt = (
            select(FileExtraction)
            .join(SourceFile, SourceFile.id == FileExtraction.source_file_id)
            .options(selectinload(FileExtraction.source_file))
            .where(SourceFile.user_id == user_id)
            .where(SourceFile.file_kind == file_kind)
            .where(SourceFile.lifecycle_status == "active")
            .order_by(FileExtraction.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_source_file(
        self,
        session: AsyncSession,
        *,
        source_file_id: UUID,
    ) -> FileExtraction | None:
        stmt = (
            select(FileExtraction)
            .where(FileExtraction.source_file_id == source_file_id)
            .order_by(FileExtraction.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_source_files(
        self,
        session: AsyncSession,
        *,
        source_file_ids: list[UUID],
    ) -> dict[UUID, FileExtraction]:
        """Batch: для списка SourceFile возвращает dict source_file_id → latest FileExtraction.

        Использует window-function подход (ROW_NUMBER) — портабельно между
        PostgreSQL/SQLite, не зависит от ``DISTINCT ON``. Пустой вход → ``{}``.
        Для SourceFile без extractions — отсутствует в dict.
        """
        if not source_file_ids:
            return {}
        from sqlalchemy import func

        rn = (
            func.row_number()
            .over(
                partition_by=FileExtraction.source_file_id,
                order_by=FileExtraction.created_at.desc(),
            )
            .label("rn")
        )
        subq = (
            select(
                FileExtraction.id,
                FileExtraction.source_file_id,
                FileExtraction.status,
                FileExtraction.parser_name,
                FileExtraction.parser_version,
                FileExtraction.extracted_text,
                FileExtraction.extracted_metadata_json,
                FileExtraction.created_at,
                FileExtraction.updated_at,
                rn,
            )
            .where(FileExtraction.source_file_id.in_(source_file_ids))
            .subquery()
        )
        stmt = select(subq).where(subq.c.rn == 1)
        result = await session.execute(stmt)
        out: dict[UUID, FileExtraction] = {}
        for row in result.all():
            extraction = FileExtraction(
                id=row.id,
                source_file_id=row.source_file_id,
                status=row.status,
                parser_name=row.parser_name,
                parser_version=row.parser_version,
                extracted_text=row.extracted_text,
                extracted_metadata_json=row.extracted_metadata_json,
            )
            extraction.created_at = row.created_at
            extraction.updated_at = row.updated_at
            out[row.source_file_id] = extraction
        return out
