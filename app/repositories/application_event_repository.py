# app\repositories\application_event_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationEvent


class ApplicationEventRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        event_type: str,
        title: str | None = None,
        description: str | None = None,
        meta_json: dict | None = None,
    ) -> ApplicationEvent:
        event = ApplicationEvent(
            application_id=application_id,
            event_type=event_type,
            title=title,
            description=description,
            meta_json=meta_json or {},
        )
        session.add(event)
        await session.flush()
        return event

    async def list_by_application_id(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
    ) -> list[ApplicationEvent]:
        stmt = (
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())