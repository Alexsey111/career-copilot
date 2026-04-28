# app\repositories\application_record_repository.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ApplicationRecord


class ApplicationRecordRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        resume_document_id: UUID | None,
        cover_letter_document_id: UUID | None,
        status: str,
        channel: str | None,
        applied_at: datetime | None,
        outcome: str | None,
        notes: str | None,
    ) -> ApplicationRecord:
        application = ApplicationRecord(
            user_id=user_id,
            vacancy_id=vacancy_id,
            resume_document_id=resume_document_id,
            cover_letter_document_id=cover_letter_document_id,
            status=status,
            channel=channel,
            applied_at=applied_at,
            outcome=outcome,
            notes=notes,
        )
        session.add(application)
        await session.flush()
        return application

    async def get_by_id(
        self,
        session: AsyncSession,
        application_id: UUID,
    ) -> ApplicationRecord | None:
        stmt = select(ApplicationRecord).where(ApplicationRecord.id == application_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id_and_vacancy_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
    ) -> ApplicationRecord | None:
        stmt = (
            select(ApplicationRecord)
            .where(ApplicationRecord.user_id == user_id)
            .where(ApplicationRecord.vacancy_id == vacancy_id)
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> list[ApplicationRecord]:
        stmt = (
            select(ApplicationRecord)
            .options(selectinload(ApplicationRecord.vacancy))
            .where(ApplicationRecord.user_id == user_id)
            .order_by(ApplicationRecord.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
