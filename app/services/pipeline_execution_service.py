# app\services\pipeline_execution_service.py

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from app.domain.pipeline_models import (
    CareerCopilotRun,
    PipelineEvent,
    PipelineEventType,
    PipelineExecutionStep,
    PipelineExecutionSummary,
    PipelineStatus,
    EventSeverity,
    StepStatus,
)
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.schemas.pipeline_schemas import ExecutionUpdateRequest

logger = logging.getLogger(__name__)


class PipelineExecutionService:
    """Service for managing pipeline execution lifecycle."""

    def __init__(self, repository: SQLAlchemyAsyncPipelineRepository) -> None:
        self._repository = repository

    async def start_execution(
        self,
        user_id: UUID,
        vacancy_id: Optional[UUID] = None,
        profile_id: Optional[UUID] = None,
        pipeline_version: str = "v1.0",
        calibration_version: Optional[str] = None,
    ) -> CareerCopilotRun:
        """Start a new pipeline execution."""
        logger.info(
            "Starting pipeline execution",
            extra={
                "user_id": str(user_id),
                "vacancy_id": str(vacancy_id) if vacancy_id else None,
                "profile_id": str(profile_id) if profile_id else None,
                "pipeline_version": pipeline_version,
            },
        )

        execution = await self._repository.create_execution(
            user_id=user_id,
            vacancy_id=vacancy_id,
            profile_id=profile_id,
            pipeline_version=pipeline_version,
        )

        await self._repository.update_execution(
            execution_id=UUID(execution.id),
            status=PipelineStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            calibration_version=calibration_version,
        )

        return execution

    async def complete_execution(
        self,
        execution_id: UUID,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        resume_document_id: Optional[UUID] = None,
        evaluation_snapshot_id: Optional[UUID] = None,
        review_id: Optional[UUID] = None,
    ) -> None:
        """Mark pipeline execution as completed."""
        logger.info("Completing pipeline execution", extra={"execution_id": str(execution_id)})

        await self._repository.update_execution(
            execution_id=execution_id,
            status=PipelineStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            artifacts=artifacts,
            metrics=metrics,
            resume_document_id=resume_document_id,
            evaluation_snapshot_id=evaluation_snapshot_id,
            review_id=review_id,
        )

        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.PIPELINE_COMPLETED,
            payload={
                "artifacts_count": len(artifacts) if artifacts else 0,
                "metrics_count": len(metrics) if metrics else 0,
            },
            severity=EventSeverity.INFO,
        )

    async def fail_execution(
        self,
        execution_id: UUID,
        error_code: str,
        error_message: str,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        """Mark pipeline execution as failed."""
        logger.error(
            "Pipeline execution failed",
            extra={"execution_id": str(execution_id), "error_code": error_code},
        )

        await self._repository.update_execution(
            execution_id=execution_id,
            status=PipelineStatus.FAILED,
            failed_at=datetime.now(timezone.utc),
            error_code=error_code,
            error_message=error_message,
            artifacts=artifacts,
            metrics=metrics,
        )

        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.PIPELINE_FAILED,
            payload={
                "error_code": error_code,
                "error_message": error_message,
            },
            severity=EventSeverity.ERROR,
        )

    async def update_pipeline_status(
        self,
        execution_id: UUID,
        status: PipelineStatus,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update pipeline execution status to a specific state."""
        logger.info(
            "Updating pipeline status",
            extra={"execution_id": str(execution_id), "status": status.value},
        )

        await self._repository.update_execution(
            execution_id=execution_id,
            status=status,
            artifacts=artifacts,
            metrics=metrics,
        )

        # Create event for status change (only for major transitions)
        if status in [PipelineStatus.RUNNING, PipelineStatus.COMPLETED, PipelineStatus.FAILED]:
            event_type = {
                PipelineStatus.RUNNING: PipelineEventType.PIPELINE_STARTED,
                PipelineStatus.COMPLETED: PipelineEventType.PIPELINE_COMPLETED,
                PipelineStatus.FAILED: PipelineEventType.PIPELINE_FAILED,
            }[status]
            await self._repository.create_event(
                execution_id=execution_id,
                event_type=event_type,
                payload={"new_status": status.value},
                severity=EventSeverity.INFO,
            )

    async def set_profile_loading(self, execution_id: UUID) -> None:
        """Set pipeline status to profile loading."""
        await self.update_pipeline_status(execution_id, PipelineStatus.PROFILE_LOADING)

    async def set_vacancy_analysis(self, execution_id: UUID) -> None:
        """Set pipeline status to vacancy analysis."""
        await self.update_pipeline_status(execution_id, PipelineStatus.VACANCY_ANALYSIS)

    async def set_achievement_retrieval(self, execution_id: UUID) -> None:
        """Set pipeline status to achievement retrieval."""
        await self.update_pipeline_status(execution_id, PipelineStatus.ACHIEVEMENT_RETRIEVAL)

    async def set_coverage_mapping(self, execution_id: UUID) -> None:
        """Set pipeline status to coverage mapping."""
        await self.update_pipeline_status(execution_id, PipelineStatus.COVERAGE_MAPPING)

    async def set_document_generation(self, execution_id: UUID) -> None:
        """Set pipeline status to document generation."""
        await self.update_pipeline_status(execution_id, PipelineStatus.DOCUMENT_GENERATION)

    async def set_document_evaluation(self, execution_id: UUID) -> None:
        """Set pipeline status to document evaluation."""
        await self.update_pipeline_status(execution_id, PipelineStatus.DOCUMENT_EVALUATION)

    async def set_readiness_scoring(self, execution_id: UUID) -> None:
        """Set pipeline status to readiness scoring."""
        await self.update_pipeline_status(execution_id, PipelineStatus.READINESS_SCORING)

    async def set_review_gate(self, execution_id: UUID) -> None:
        """Set pipeline status to review gate."""
        await self.update_pipeline_status(execution_id, PipelineStatus.REVIEW_GATE)

    async def update_execution(
        self,
        execution_id: UUID,
        update_data: ExecutionUpdateRequest,
    ) -> Optional[CareerCopilotRun]:
        """Update pipeline execution with the provided data."""
        # Get current execution
        execution = await self._repository.get_execution(execution_id)
        if not execution:
            return None

        # Prepare update data
        update_kwargs = {}
        if update_data.status is not None:
            update_kwargs["status"] = PipelineStatus(update_data.status.value)
        if update_data.review_required is not None:
            update_kwargs["review_required"] = update_data.review_required
        if update_data.review_completed is not None:
            update_kwargs["review_completed"] = update_data.review_completed
        if update_data.started_at is not None:
            update_kwargs["started_at"] = update_data.started_at
        if update_data.completed_at is not None:
            update_kwargs["completed_at"] = update_data.completed_at
        if update_data.failed_at is not None:
            update_kwargs["failed_at"] = update_data.failed_at
        if update_data.execution_duration_ms is not None:
            update_kwargs["execution_duration_ms"] = update_data.execution_duration_ms
        if update_data.evaluation_duration_ms is not None:
            update_kwargs["evaluation_duration_ms"] = update_data.evaluation_duration_ms
        if update_data.mutation_duration_ms is not None:
            update_kwargs["mutation_duration_ms"] = update_data.mutation_duration_ms
        if update_data.error_code is not None:
            update_kwargs["error_code"] = update_data.error_code
        if update_data.error_message is not None:
            update_kwargs["error_message"] = update_data.error_message
        if update_data.artifacts_json is not None:
            update_kwargs["artifacts"] = update_data.artifacts_json
        if update_data.metrics_json is not None:
            update_kwargs["metrics"] = update_data.metrics_json
        if update_data.resume_document_id is not None:
            update_kwargs["resume_document_id"] = update_data.resume_document_id
        if update_data.evaluation_snapshot_id is not None:
            update_kwargs["evaluation_snapshot_id"] = update_data.evaluation_snapshot_id
        if update_data.review_id is not None:
            update_kwargs["review_id"] = update_data.review_id

        # Update execution
        await self._repository.update_execution(execution_id=execution_id, **update_kwargs)

        # Return updated execution
        return await self._repository.get_execution(execution_id)

    async def start_step(
        self,
        execution_id: UUID,
        step_name: str,
        input_artifact_ids: Optional[list[str]] = None,
    ) -> PipelineExecutionStep:
        """Start a new pipeline step."""
        logger.debug(
            "Starting pipeline step",
            extra={"execution_id": str(execution_id), "step_name": step_name},
        )

        step = await self._repository.create_step(
            execution_id=execution_id,
            step_name=step_name,
            input_artifact_ids=input_artifact_ids,
        )

        await self._repository.update_step(
            step_id=UUID(step.id),
            status=StepStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc),
        )

        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.STEP_STARTED,
            payload={"step_name": step_name},
            step_id=UUID(step.id),
            severity=EventSeverity.DEBUG,
        )

        return step

    async def complete_step(
        self,
        step_id: UUID,
        output_artifact_ids: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Mark pipeline step as completed."""
        step = await self._repository.get_step(step_id)
        if not step:
            raise ValueError(f"Step {step_id} not found")

        completed_at = datetime.now(timezone.utc)
        duration_ms = None
        if step.started_at:
            duration_ms = int((completed_at - step.started_at).total_seconds() * 1000)

        await self._repository.update_step(
            step_id=step_id,
            status=StepStatus.COMPLETED.value,
            completed_at=completed_at,
            duration_ms=duration_ms,
            output_artifact_ids=output_artifact_ids,
            metadata=metadata,
        )

        await self._repository.create_event(
            execution_id=UUID(step.execution_id),
            event_type=PipelineEventType.STEP_COMPLETED,
            payload={"output_artifacts_count": len(output_artifact_ids) if output_artifact_ids else 0},
            step_id=step_id,
            severity=EventSeverity.DEBUG,
        )

    async def fail_step(
        self,
        step_id: UUID,
        error_message: str,
    ) -> None:
        """Mark pipeline step as failed."""
        step = await self._repository.get_step(step_id)
        if not step:
            raise ValueError(f"Step {step_id} not found")

        completed_at = datetime.now(timezone.utc)
        duration_ms = None
        if step.started_at:
            duration_ms = int((completed_at - step.started_at).total_seconds() * 1000)

        await self._repository.update_step(
            step_id=step_id,
            status=StepStatus.FAILED.value,
            completed_at=completed_at,
            duration_ms=duration_ms,
            error_message=error_message,
        )

        await self._repository.create_event(
            execution_id=UUID(step.execution_id),
            event_type=PipelineEventType.STEP_FAILED,
            payload={"error_message": error_message},
            step_id=step_id,
            severity=EventSeverity.ERROR,
        )

    async def record_evaluation_failed(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        error_details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record evaluation failure event."""
        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.EVALUATION_FAILED,
            payload=error_details or {},
            step_id=step_id,
            severity=EventSeverity.WARNING,
        )

    async def record_review_required(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        review_reason: Optional[str] = None,
    ) -> None:
        """Record that manual review is required."""
        await self._repository.update_execution(
            execution_id=execution_id,
            review_required=True,
            status=PipelineStatus.REVIEW_GATE,
            error_message=review_reason,
        )

        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.REVIEW_REQUIRED,
            payload={"review_reason": review_reason},
            step_id=step_id,
            severity=EventSeverity.INFO,
        )

    async def record_review_completed(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        review_summary: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record that manual review is completed."""
        await self._repository.update_execution(
            execution_id=execution_id,
            review_completed=True,
        )

        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.REVIEW_COMPLETED,
            payload=review_summary or {"review_completed": True},
            step_id=step_id,
            severity=EventSeverity.INFO,
        )

    async def record_recommendation_generated(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        recommendation_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record that a recommendation was generated."""
        await self._repository.create_event(
            execution_id=execution_id,
            event_type=PipelineEventType.RECOMMENDATION_GENERATED,
            payload=recommendation_data or {},
            step_id=step_id,
            severity=EventSeverity.INFO,
        )

    async def get_execution_summary(self, execution_id: UUID) -> Optional[PipelineExecutionSummary]:
        """Get full execution summary with steps and events."""
        return await self._repository.get_execution_with_steps_and_events(execution_id)

    async def get_user_executions(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a user."""
        return await self._repository.get_executions_for_user(user_id, limit, offset, status)

    async def get_vacancy_executions(
        self,
        vacancy_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a vacancy."""
        return await self._repository.get_executions_for_vacancy(vacancy_id, limit, offset)
