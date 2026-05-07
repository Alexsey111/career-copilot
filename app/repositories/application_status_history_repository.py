# app\repositories\application_status_history_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationStatusHistory


class ApplicationStatusHistoryRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        previous_status: str | None,
        new_status: str,
        notes: str | None,
    ) -> ApplicationStatusHistory:
        history = ApplicationStatusHistory(
            application_id=application_id,
            previous_status=previous_status,
            new_status=new_status,
            notes=notes,
        )

        session.add(history)
        await session.flush()

        return history

    async def list_by_application_id(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
    ) -> list[ApplicationStatusHistory]:
        stmt = (
            select(ApplicationStatusHistory)
            .where(
                ApplicationStatusHistory.application_id
                == application_id
            )
            .order_by(ApplicationStatusHistory.changed_at.asc())
        )

        result = await session.execute(stmt)

        return list(result.scalars().all())