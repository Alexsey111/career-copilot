# app/repositories/pipeline_execution_event_repository.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PipelineExecutionEvent


class PipelineExecutionEventRepository:
    """Repository for historical pipeline execution events."""

    async def create_event(
        self,
        session: AsyncSession,
        *,
        execution_id: UUID,
        event_type: str,
        payload_json: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> PipelineExecutionEvent:
        event = PipelineExecutionEvent(
            execution_id=execution_id,
            event_type=event_type,
            payload_json=payload_json or {},
            created_at=created_at or datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()
        await session.refresh(event)
        return event

    async def get_execution_events(
        self,
        session: AsyncSession,
        *,
        execution_id: UUID,
    ) -> list[PipelineExecutionEvent]:
        stmt = (
            select(PipelineExecutionEvent)
            .where(PipelineExecutionEvent.execution_id == execution_id)
            .order_by(PipelineExecutionEvent.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_events(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
    ) -> list[PipelineExecutionEvent]:
        stmt = (
            select(PipelineExecutionEvent)
            .order_by(PipelineExecutionEvent.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
