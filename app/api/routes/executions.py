"""app/api/routes/executions.py."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domain.pipeline_models import PipelineStatus
from app.models import Vacancy, VacancyAnalysis
from app.repositories.pipeline_execution_event_repository import PipelineExecutionEventRepository
from app.repositories.pipeline_execution_repository import PipelineExecutionRepository
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.schemas.pipeline_schemas import (
    DeadLetterJobResponse,
    ExecutionFamilyResponse,
    ExecutionEventTimelineItem,
    ExecutionLineageGraphResponse,
    ExecutionResumeRequest,
    ExecutionResumeResponse,
    ExecutionRuntimeSnapshotResponse,
    ExecutionTimelineItem,
    PhaseAnalyticsItem,
    PipelineExecutionResponse,
)
from app.services.execution_observability_service import ExecutionObservabilityService
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.pipeline_job_queue import RedisPipelineJobQueue
from app.services.stuck_execution_service import StuckExecutionService


router = APIRouter(prefix="/executions", tags=["executions"])


def _to_execution_response(execution) -> PipelineExecutionResponse:
    return PipelineExecutionResponse(
        id=UUID(execution.id),
        user_id=UUID(execution.user_id),
        document_id=UUID(execution.document_id) if execution.document_id else None,
        vacancy_id=UUID(execution.vacancy_id) if execution.vacancy_id else None,
        profile_id=UUID(execution.profile_id) if execution.profile_id else None,
        status=execution.status.value,
        review_required=execution.review_required,
        review_completed=execution.review_completed,
        pipeline_version=execution.pipeline_version,
        calibration_version=execution.calibration_version,
        idempotency_key=execution.idempotency_key,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        failed_at=execution.failed_at,
        execution_duration_ms=execution.execution_duration_ms,
        evaluation_duration_ms=execution.evaluation_duration_ms,
        mutation_duration_ms=execution.mutation_duration_ms,
        retry_count=execution.retry_count,
        failed_step=execution.failed_step,
        last_error=execution.last_error,
        resume_document_id=UUID(execution.resume_document_id) if execution.resume_document_id else None,
        evaluation_snapshot_id=UUID(execution.evaluation_snapshot_id) if execution.evaluation_snapshot_id else None,
        review_id=UUID(execution.review_id) if execution.review_id else None,
        parent_execution_id=UUID(execution.parent_execution_id) if execution.parent_execution_id else None,
        lineage_kind=execution.lineage_kind,
        lineage_reason=execution.lineage_reason,
        lineage_metadata_json=execution.lineage_metadata,
        error_code=execution.error_code,
        error_message=execution.error_message,
        artifacts_json=execution.artifacts,
        metrics_json=execution.metrics,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


async def _resolve_inherited_evaluation_snapshot_id(
    *,
    db: AsyncSession,
    parent_execution,
) -> UUID | None:
    if not parent_execution.evaluation_snapshot_id or not parent_execution.vacancy_id:
        return None

    snapshot_id = UUID(parent_execution.evaluation_snapshot_id)
    vacancy_id = UUID(parent_execution.vacancy_id)
    snapshot = await db.get(VacancyAnalysis, snapshot_id)
    vacancy = await db.get(Vacancy, vacancy_id)

    if snapshot is None or vacancy is None:
        return None
    if snapshot.vacancy_id != vacancy.id:
        return None
    if vacancy.updated_at and snapshot.created_at < vacancy.updated_at:
        return None

    return snapshot_id


@router.get("/runtime-snapshot", response_model=ExecutionRuntimeSnapshotResponse)
async def get_execution_runtime_snapshot(
    db: AsyncSession = Depends(get_db_session),
) -> ExecutionRuntimeSnapshotResponse:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    pipeline_service = PipelineExecutionService(repository=pipeline_repo)
    stuck_service = StuckExecutionService(pipeline_service=pipeline_service)
    observability_service = ExecutionObservabilityService(
        pipeline_repository=PipelineExecutionRepository(),
        stuck_execution_service=stuck_service,
    )

    snapshot = await observability_service.get_execution_runtime_snapshot(db)
    return ExecutionRuntimeSnapshotResponse.model_validate(snapshot)


@router.get("/dead-letter", response_model=list[DeadLetterJobResponse])
async def get_dead_letter_jobs(limit: int = 100) -> list[DeadLetterJobResponse]:
    queue = RedisPipelineJobQueue()
    jobs = await queue.get_dead_letter_jobs(limit=limit)

    return [
        DeadLetterJobResponse(
            execution_id=job.get("execution_id"),
            retry_count=int(job["retry_count"]) if job.get("retry_count") is not None else None,
            failure_category=job.get("failure_category"),
            dead_letter_reason=job.get("dead_letter_reason"),
            dead_lettered_at=job.get("dead_lettered_at"),
        )
        for job in jobs
    ]


@router.get("/phase-analytics", response_model=list[PhaseAnalyticsItem])
async def get_phase_analytics(
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
) -> list[PhaseAnalyticsItem]:
    repository = PipelineExecutionRepository()
    aggregates = await repository.get_phase_runtime_aggregates(db, limit=limit)

    return [
        PhaseAnalyticsItem(
            step_name=aggregate.step_name,
            total_count=aggregate.total_count,
            completed_count=aggregate.completed_count,
            failed_count=aggregate.failed_count,
            avg_duration_ms=aggregate.avg_duration_ms,
            max_duration_ms=aggregate.max_duration_ms,
            retry_count=aggregate.retry_count,
            failure_rate=(
                aggregate.failed_count / aggregate.total_count
                if aggregate.total_count > 0
                else 0.0
            ),
        )
        for aggregate in aggregates
    ]


@router.post(
    "/{execution_id}/resume",
    response_model=ExecutionResumeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_execution(
    execution_id: UUID,
    request: ExecutionResumeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ExecutionResumeResponse:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)

    parent_execution = await pipeline_repo.get_execution(execution_id)
    if parent_execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    if parent_execution.status != PipelineStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only failed executions can be resumed",
        )

    inherited_evaluation_snapshot_id = await _resolve_inherited_evaluation_snapshot_id(
        db=db,
        parent_execution=parent_execution,
    )
    lineage_metadata = {
        "resume_from_phase": request.resume_from_phase,
        "source_execution_status": parent_execution.status.value,
    }
    if inherited_evaluation_snapshot_id is not None:
        lineage_metadata["inherited_artifacts"] = {
            "evaluation_snapshot_id": str(inherited_evaluation_snapshot_id),
        }

    child_execution = await pipeline_repo.create_execution(
        user_id=UUID(parent_execution.user_id),
        vacancy_id=UUID(parent_execution.vacancy_id),
        profile_id=UUID(parent_execution.profile_id) if parent_execution.profile_id else None,
        document_id=UUID(parent_execution.document_id) if parent_execution.document_id else None,
        pipeline_version=parent_execution.pipeline_version,
        calibration_version=parent_execution.calibration_version,
        idempotency_key=None,
        parent_execution_id=UUID(parent_execution.id),
        lineage_kind="resume",
        lineage_reason=request.reason,
        lineage_metadata=lineage_metadata,
    )
    if inherited_evaluation_snapshot_id is not None:
        await pipeline_repo.update_execution(
            UUID(child_execution.id),
            evaluation_snapshot_id=inherited_evaluation_snapshot_id,
            commit=False,
        )

    queue = RedisPipelineJobQueue()
    await queue.enqueue_pipeline_run(
        execution_id=UUID(child_execution.id),
        user_id=UUID(child_execution.user_id),
        document_id=UUID(child_execution.document_id),
        vacancy_id=UUID(child_execution.vacancy_id),
        pipeline_version=child_execution.pipeline_version or "v1.0",
        calibration_version=child_execution.calibration_version,
        idempotency_key=None,
    )

    await db.commit()

    return ExecutionResumeResponse(
        parent_execution_id=execution_id,
        child_execution_id=UUID(child_execution.id),
        lineage_kind="resume",
    )


@router.get("/{execution_id}/family", response_model=ExecutionFamilyResponse)
async def get_execution_family(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ExecutionFamilyResponse:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    current_execution = await pipeline_repo.get_execution(execution_id)
    if current_execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    parent_execution = None
    if current_execution.parent_execution_id:
        parent_execution = await pipeline_repo.get_execution(UUID(current_execution.parent_execution_id))

    child_executions = await pipeline_repo.get_child_executions(execution_id)
    return ExecutionFamilyResponse(
        parent=_to_execution_response(parent_execution) if parent_execution is not None else None,
        current=_to_execution_response(current_execution),
        children=[_to_execution_response(execution) for execution in child_executions],
    )


@router.get("/{execution_id}/lineage-graph", response_model=ExecutionLineageGraphResponse)
async def get_execution_lineage_graph(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ExecutionLineageGraphResponse:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    execution = await pipeline_repo.get_execution(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    child_executions = await pipeline_repo.get_child_executions(execution_id)
    return ExecutionLineageGraphResponse(
        execution_id=UUID(execution.id),
        parent_execution_id=UUID(execution.parent_execution_id) if execution.parent_execution_id else None,
        children=[UUID(child.id) for child in child_executions],
        inherited_artifacts=(execution.lineage_metadata or {}).get("inherited_artifacts", {}),
    )


@router.get("/{execution_id}/children", response_model=list[PipelineExecutionResponse])
async def get_child_executions(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[PipelineExecutionResponse]:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    parent_execution = await pipeline_repo.get_execution(execution_id)
    if parent_execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    child_executions = await pipeline_repo.get_child_executions(execution_id)
    return [_to_execution_response(execution) for execution in child_executions]


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


@router.get("/{execution_id}/timeline", response_model=list[ExecutionTimelineItem])
async def get_execution_timeline(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ExecutionTimelineItem]:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    execution = await pipeline_repo.get_execution(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    event_repo = PipelineExecutionEventRepository()
    events = await event_repo.get_execution_events(db, execution_id=execution_id)

    timeline: list[ExecutionTimelineItem] = []
    for event in events:
        payload = event.payload_json or {}
        score = None
        if event.event_type == "evaluation_completed":
            score_value = payload.get("score")
            if isinstance(score_value, (int, float)):
                score = float(score_value)
        timeline.append(
            ExecutionTimelineItem(
                type=event.event_type,
                timestamp=event.created_at,
                score=score,
                trace_id=payload.get("trace_id"),
                correlation_id=payload.get("correlation_id"),
            )
        )

    return timeline


@router.post("/{execution_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_execution(
    execution_id: UUID,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    pipeline_service = PipelineExecutionService(repository=pipeline_repo)

    execution = await pipeline_repo.get_execution(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution not found",
        )

    try:
        await pipeline_service.cancel_execution(
            execution_id=execution_id,
            reason=reason,
            session=db,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return {
        "execution_id": str(execution_id),
        "status": "cancelled",
    }
