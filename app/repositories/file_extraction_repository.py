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
    ) -> FileExtraction | None:
        stmt = (
            select(FileExtraction)
            .options(selectinload(FileExtraction.source_file))
            .where(FileExtraction.id == extraction_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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