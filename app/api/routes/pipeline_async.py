"""Async pipeline enqueue endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.tracing import get_trace_context
from app.schemas.pipeline_schemas import PipelineExecutionCreate, PipelineRunQueuedResponse
from app.services.pipeline_job_queue import RedisPipelineJobQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def get_pipeline_job_queue() -> RedisPipelineJobQueue:
    return RedisPipelineJobQueue()


@router.post("/run", response_model=PipelineRunQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_pipeline_run(
    execution_data: PipelineExecutionCreate,
    queue: RedisPipelineJobQueue = Depends(get_pipeline_job_queue),
) -> PipelineRunQueuedResponse:
    try:
        dispatch = await queue.enqueue_pipeline_run(
            user_id=execution_data.user_id,
            document_id=execution_data.document_id,
            vacancy_id=execution_data.vacancy_id,
            pipeline_version=execution_data.pipeline_version,
            calibration_version=execution_data.calibration_version,
            idempotency_key=execution_data.idempotency_key,
            correlation_id=get_trace_context().correlation_id,
        )
        return PipelineRunQueuedResponse(
            execution_id=dispatch.execution_id,
            job_id=dispatch.job_id,
            status="queued" if dispatch.queued else "already_queued",
            queued=dispatch.queued,
            idempotency_key=dispatch.idempotency_key,
            correlation_id=dispatch.correlation_id,
            queued_at=dispatch.queued_at,
        )
    except Exception as exc:
        logger.exception("Failed to enqueue pipeline run")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue pipeline run: {exc}",
        )
