"""app/api/routes/executions.py."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.pipeline_execution_event_repository import PipelineExecutionEventRepository
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.schemas.pipeline_schemas import ExecutionEventTimelineItem


router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{execution_id}/events", response_model=list[ExecutionEventTimelineItem])
async def get_execution_events(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ExecutionEventTimelineItem]:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    execution = await pipeline_repo.get_execution(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    event_repo = PipelineExecutionEventRepository()
    events = await event_repo.get_execution_events(db, execution_id=execution_id)
    return [
        ExecutionEventTimelineItem(
            event_type=event.event_type,
            created_at=event.created_at,
            payload_json=event.payload_json,
        )
        for event in events
    ]
