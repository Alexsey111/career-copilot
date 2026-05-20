# app\repositories\application_event_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.application_events import ApplicationEventType
from app.models import ApplicationEvent


class ApplicationEventRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        application_id: UUID,
        event_type: str | ApplicationEventType,
        title: str | None = None,
        description: str | None = None,
        meta_json: dict | None = None,
    ) -> ApplicationEvent:
        event_type_value = (
            event_type.value if isinstance(event_type, ApplicationEventType) else str(event_type)
        )
        event = ApplicationEvent(
            application_id=application_id,
            event_type=event_type_value,
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
