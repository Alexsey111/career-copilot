from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.pipeline_schemas import (
    PipelineExecutionCreate,
    PipelineExecutionResponse,
    PipelineExecutionSummaryResponse,
    PipelineExecutionListResponse,
    PipelineExecutionStepResponse,
    PipelineEventResponse,
    PipelineStatusEnum,
    StepStatusEnum,
    ExecutionUpdateRequest,
    StepUpdateRequest,
    CareerCopilotRunResponse,
)
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.review_workspace_service import ReviewWorkspaceService
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/career-copilot/run", tags=["Career Copilot Run"])


def get_pipeline_service(db: AsyncSession) -> PipelineExecutionService:
    """Dependency injection for pipeline service."""
    repository = SQLAlchemyAsyncPipelineRepository(session=db)
    return PipelineExecutionService(repository=repository)


def get_review_workspace_service(db: AsyncSession) -> ReviewWorkspaceService:
    """Dependency injection for review workspace service."""
    from app.repositories.document_version_repository import DocumentVersionRepository
    from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository

    pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=db)
    return ReviewWorkspaceService(
        document_repo=DocumentVersionRepository(),
        pipeline_repo=pipeline_repo,
        vacancy_analysis_repo=VacancyAnalysisRepository(),
    )


@router.post("", response_model=PipelineExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_execution(
    execution_data: PipelineExecutionCreate,
    service: PipelineExecutionService = Depends(lambda db=None: get_pipeline_service(db)),
    db: AsyncSession = Depends(get_db_session),
):
    """Create and start a new pipeline execution."""
    try:
        execution = await service.start_execution(
            user_id=execution_data.user_id,
            vacancy_id=execution_data.vacancy_id,
            profile_id=execution_data.profile_id,
            pipeline_version=execution_data.pipeline_version,
            calibration_version=execution_data.calibration_version,
        )

        return PipelineExecutionResponse(
            id=UUID(execution.id),
            user_id=UUID(execution.user_id),
            vacancy_id=UUID(execution.vacancy_id) if execution.vacancy_id else None,
            profile_id=UUID(execution.profile_id) if execution.profile_id else None,
            status=execution.status.value,
            pipeline_version=execution.pipeline_version,
            calibration_version=execution.calibration_version,
            started_at=execution.started_at,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )
    except Exception as e:
        logger.error(f"Failed to create pipeline execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create pipeline execution: {str(e)}",
        )


@router.patch("/{execution_id}", response_model=PipelineExecutionResponse)
async def update_pipeline_execution(
    execution_id: UUID,
    update_data: ExecutionUpdateRequest,
    service: PipelineExecutionService = Depends(lambda db=None: get_pipeline_service(db)),
    db: AsyncSession = Depends(get_db_session),
):
    """Update pipeline execution status and metadata."""
    execution = await service.update_execution(execution_id, update_data)

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline execution {execution_id} not found",
        )

    return PipelineExecutionResponse(
        id=UUID(execution.id),
        user_id=UUID(execution.user_id),
        vacancy_id=UUID(execution.vacancy_id) if execution.vacancy_id else None,
        profile_id=UUID(execution.profile_id) if execution.profile_id else None,
        status=execution.status.value,
        pipeline_version=execution.pipeline_version,
        calibration_version=execution.calibration_version,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        failed_at=execution.failed_at,
        resume_document_id=UUID(execution.resume_document_id) if execution.resume_document_id else None,
        evaluation_snapshot_id=UUID(execution.evaluation_snapshot_id) if execution.evaluation_snapshot_id else None,
        review_id=UUID(execution.review_id) if execution.review_id else None,
        error_code=execution.error_code,
        error_message=execution.error_message,
        artifacts_json=execution.artifacts,
        metrics_json=execution.metrics,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


@router.get("/{execution_id}", response_model=CareerCopilotRunResponse)
async def get_career_copilot_run(
    execution_id: UUID,
    pipeline_service: PipelineExecutionService = Depends(lambda db=None: get_pipeline_service(db)),
    review_service: ReviewWorkspaceService = Depends(lambda db=None: get_review_workspace_service(db)),
    db: AsyncSession = Depends(get_db_session),
):
    """Get complete career copilot run with progress, artifacts, readiness, tasks, and review status."""
    # Get pipeline execution summary
    summary = await pipeline_service.get_execution_summary(execution_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Career copilot run {execution_id} not found",
        )

    # Try to get review workspace data
    review_workspace = None
    try:
        # Build workspace ID from execution data
        workspace_id = f"ws_{summary.execution.resume_document_id}_{summary.execution.user_id}"
        review_workspace = await review_service.build_review_workspace(
            document_id=summary.execution.resume_document_id,
            user_id=summary.execution.user_id,
            pipeline_execution_id=execution_id,
            session=db
        )
    except Exception:
        # If review workspace is not available, continue without it
        pass

    # Calculate progress
    total_steps = len(summary.steps)
    completed_steps = len(summary.completed_steps)
    progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0

    progress = {
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "failed_steps": len(summary.failed_steps),
        "percentage": progress_percentage,
        "status": summary.execution.status.value,
    }

    return CareerCopilotRunResponse(
        execution=PipelineExecutionResponse(
            id=UUID(summary.execution.id),
            user_id=UUID(summary.execution.user_id),
            vacancy_id=UUID(summary.execution.vacancy_id) if summary.execution.vacancy_id else None,
            profile_id=UUID(summary.execution.profile_id) if summary.execution.profile_id else None,
            status=summary.execution.status.value,
            pipeline_version=summary.execution.pipeline_version,
            calibration_version=summary.execution.calibration_version,
            started_at=summary.execution.started_at,
            completed_at=summary.execution.completed_at,
            failed_at=summary.execution.failed_at,
            resume_document_id=UUID(summary.execution.resume_document_id) if summary.execution.resume_document_id else None,
            evaluation_snapshot_id=UUID(summary.execution.evaluation_snapshot_id) if summary.execution.evaluation_snapshot_id else None,
            review_id=UUID(summary.execution.review_id) if summary.execution.review_id else None,
            error_code=summary.execution.error_code,
            error_message=summary.execution.error_message,
            artifacts_json=summary.execution.artifacts,
            metrics_json=summary.execution.metrics,
            created_at=summary.execution.created_at,
            updated_at=summary.execution.updated_at,
        ),
        steps=[
            PipelineExecutionStepResponse(
                id=UUID(step.id),
                execution_id=UUID(step.execution_id),
                step_name=step.step_name,
                status=step.status.value,
                started_at=step.started_at,
                completed_at=step.completed_at,
                duration_ms=step.duration_ms,
                input_artifact_ids=step.input_artifact_ids,
                output_artifact_ids=step.output_artifact_ids,
                error_message=step.error_message,
                metadata_json=step.metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for step in summary.steps
        ],
        events=[
            PipelineEventResponse(
                id=UUID(event.id),
                execution_id=UUID(event.execution_id),
                event_type=event.event_type.value,
                step_id=UUID(event.step_id) if event.step_id else None,
                payload_json=event.payload,
                severity=event.severity.value,
                created_at=event.created_at,
            )
            for event in summary.events
        ],
        total_duration_ms=summary.total_duration_ms,
        failed_steps=[
            PipelineExecutionStepResponse(
                id=UUID(step.id),
                execution_id=UUID(step.execution_id),
                step_name=step.step_name,
                status=step.status.value,
                started_at=step.started_at,
                completed_at=step.completed_at,
                duration_ms=step.duration_ms,
                input_artifact_ids=step.input_artifact_ids,
                output_artifact_ids=step.output_artifact_ids,
                error_message=step.error_message,
                metadata_json=step.metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for step in summary.failed_steps
        ],
        completed_steps=[
            PipelineExecutionStepResponse(
                id=UUID(step.id),
                execution_id=UUID(step.execution_id),
                step_name=step.step_name,
                status=step.status.value,
                started_at=step.started_at,
                completed_at=step.completed_at,
                duration_ms=step.duration_ms,
                input_artifact_ids=step.input_artifact_ids,
                output_artifact_ids=step.output_artifact_ids,
                error_message=step.error_message,
                metadata_json=step.metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for step in summary.completed_steps
        ],
        progress=progress,
        artifacts=summary.execution.artifacts or {},
        readiness=review_workspace.readiness_score if review_workspace else None,
        tasks=review_workspace.recommendation_tasks if review_workspace else [],
        review_status=review_workspace.status if review_workspace else "draft",
    )


@router.get("/user/{user_id}", response_model=PipelineExecutionListResponse)
async def get_user_executions(
    user_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[PipelineStatusEnum] = None,
    service: PipelineExecutionService = Depends(lambda db=None: get_pipeline_service(db)),
    db: AsyncSession = Depends(get_db_session),
):
    """Get pipeline executions for a user."""
    executions = await service.get_user_executions(
        user_id=user_id,
        limit=limit,
        offset=offset,
        status=status.value if status else None,
    )

    return PipelineExecutionListResponse(
        items=[
            PipelineExecutionResponse(
                id=UUID(exec.id),
                user_id=UUID(exec.user_id),
                vacancy_id=UUID(exec.vacancy_id) if exec.vacancy_id else None,
                profile_id=UUID(exec.profile_id) if exec.profile_id else None,
                status=exec.status.value,
                pipeline_version=exec.pipeline_version,
                calibration_version=exec.calibration_version,
                started_at=exec.started_at,
                completed_at=exec.completed_at,
                failed_at=exec.failed_at,
                resume_document_id=UUID(exec.resume_document_id) if exec.resume_document_id else None,
                evaluation_snapshot_id=UUID(exec.evaluation_snapshot_id) if exec.evaluation_snapshot_id else None,
                review_id=UUID(exec.review_id) if exec.review_id else None,
                error_code=exec.error_code,
                error_message=exec.error_message,
                artifacts_json=exec.artifacts,
                metrics_json=exec.metrics,
                created_at=exec.created_at,
                updated_at=exec.updated_at,
            )
            for exec in executions
        ],
        total=len(executions),
        limit=limit,
        offset=offset,
    )


@router.get("/vacancy/{vacancy_id}", response_model=PipelineExecutionListResponse)
async def get_vacancy_executions(
    vacancy_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PipelineExecutionService = Depends(lambda db=None: get_pipeline_service(db)),
    db: AsyncSession = Depends(get_db_session),
):
    """Get pipeline executions for a vacancy."""
    executions = await service.get_vacancy_executions(
        vacancy_id=vacancy_id,
        limit=limit,
        offset=offset,
    )

    return PipelineExecutionListResponse(
        items=[
            PipelineExecutionResponse(
                id=UUID(exec.id),
                user_id=UUID(exec.user_id),
                vacancy_id=UUID(exec.vacancy_id) if exec.vacancy_id else None,
                profile_id=UUID(exec.profile_id) if exec.profile_id else None,
                status=exec.status.value,
                pipeline_version=exec.pipeline_version,
                calibration_version=exec.calibration_version,
                started_at=exec.started_at,
                completed_at=exec.completed_at,
                failed_at=exec.failed_at,
                resume_document_id=UUID(exec.resume_document_id) if exec.resume_document_id else None,
                evaluation_snapshot_id=UUID(exec.evaluation_snapshot_id) if exec.evaluation_snapshot_id else None,
                review_id=UUID(exec.review_id) if exec.review_id else None,
                error_code=exec.error_code,
                error_message=exec.error_message,
                artifacts_json=exec.artifacts,
                metrics_json=exec.metrics,
                created_at=exec.created_at,
                updated_at=exec.updated_at,
            )
            for exec in executions
        ],
        total=len(executions),
        limit=limit,
        offset=offset,
    )
