# app\services\pipeline_execution_service.py

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
from app.domain.execution_event_payloads import (
    ExecutionCompletedPayload,
    ExecutionFailedPayload,
    ExecutionStartedPayload,
    EvaluationCompletedPayload,
    EvaluationFailedPayload,
    RecommendationAppliedPayload,
    ReviewCompletedPayload,
    ReviewRequiredPayload,
    StepCompletedPayload,
    StepFailedPayload,
    StepStartedPayload,
    serialize_execution_event_payload,
)
from app.domain.pipeline_execution_status import PipelineExecutionStatus
from app.domain.execution_events import ExecutionEventType
from app.repositories.pipeline_execution_event_repository import (
    PipelineExecutionEventRepository,
)
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.schemas.pipeline_schemas import ExecutionUpdateRequest

logger = logging.getLogger(__name__)


class PipelineExecutionService:
    """Service for managing pipeline execution lifecycle."""

    def __init__(
        self,
        repository: SQLAlchemyAsyncPipelineRepository,
        event_repository: PipelineExecutionEventRepository | None = None,
    ) -> None:
        self._repository = repository
        self._event_repository = event_repository or PipelineExecutionEventRepository()

    @staticmethod
    def _normalize_status(
        status: PipelineStatus | PipelineExecutionStatus | None,
    ) -> PipelineExecutionStatus | None:
        if status is None:
            return None

        if isinstance(status, PipelineExecutionStatus):
            return status

        return {
            PipelineStatus.PENDING: PipelineExecutionStatus.CREATED,
            PipelineStatus.RUNNING: PipelineExecutionStatus.RUNNING,
            PipelineStatus.REVIEW_GATE: PipelineExecutionStatus.REVIEW_REQUIRED,
            PipelineStatus.COMPLETED: PipelineExecutionStatus.COMPLETED,
            PipelineStatus.FAILED: PipelineExecutionStatus.FAILED,
            PipelineStatus.CANCELLED: PipelineExecutionStatus.CANCELLED,
        }.get(status, None)

    @staticmethod
    def _to_repository_status(status: PipelineExecutionStatus) -> PipelineStatus:
        return {
            PipelineExecutionStatus.CREATED: PipelineStatus.PENDING,
            PipelineExecutionStatus.RUNNING: PipelineStatus.RUNNING,
            PipelineExecutionStatus.REVIEW_REQUIRED: PipelineStatus.REVIEW_GATE,
            PipelineExecutionStatus.COMPLETED: PipelineStatus.COMPLETED,
            PipelineExecutionStatus.FAILED: PipelineStatus.FAILED,
            PipelineExecutionStatus.CANCELLED: PipelineStatus.CANCELLED,
        }[status]

    def _transition_status(
        self,
        current: PipelineStatus | PipelineExecutionStatus | None,
        target: PipelineStatus | PipelineExecutionStatus,
    ) -> PipelineExecutionStatus:
        current_state = self._normalize_status(current)
        target_state = self._normalize_status(target)

        if target_state is None:
            raise ValueError(f"Unsupported target status: {target!r}")

        allowed_transitions: dict[PipelineExecutionStatus, set[PipelineExecutionStatus]] = {
            PipelineExecutionStatus.CREATED: {PipelineExecutionStatus.RUNNING},
            PipelineExecutionStatus.RUNNING: {
                PipelineExecutionStatus.REVIEW_REQUIRED,
                PipelineExecutionStatus.COMPLETED,
                PipelineExecutionStatus.FAILED,
            },
            PipelineExecutionStatus.REVIEW_REQUIRED: {
                PipelineExecutionStatus.COMPLETED,
                PipelineExecutionStatus.FAILED,
            },
            PipelineExecutionStatus.COMPLETED: set(),
            PipelineExecutionStatus.FAILED: set(),
            PipelineExecutionStatus.CANCELLED: set(),
        }

        if current_state is None:
            current_state = PipelineExecutionStatus.CREATED

        if target_state not in allowed_transitions[current_state]:
            raise ValueError(f"Invalid pipeline execution transition: {current_state.value} -> {target_state.value}")

        return target_state

    @staticmethod
    def _build_evaluation_completed_payload(
        evaluation_summary: Optional[dict[str, Any]],
    ) -> EvaluationCompletedPayload | dict[str, Any]:
        if not evaluation_summary or not evaluation_summary.get("snapshot_id"):
            return evaluation_summary or {"evaluation_completed": True}

        return EvaluationCompletedPayload(
            snapshot_id=UUID(str(evaluation_summary["snapshot_id"])),
            score=float(evaluation_summary.get("overall_score", 0.0)),
            duration_ms=int(evaluation_summary.get("duration_ms", 0)),
            phase=str(evaluation_summary.get("phase", "initial")),
        )

    @staticmethod
    def _build_recommendation_applied_payload(
        recommendation_data: Optional[dict[str, Any]],
    ) -> RecommendationAppliedPayload | dict[str, Any]:
        if not recommendation_data:
            return {}

        document_id = recommendation_data.get("document_id")
        if not document_id:
            return recommendation_data

        return RecommendationAppliedPayload(
            recommendation_id=str(recommendation_data.get("recommendation_id", "")),
            task_type=str(recommendation_data.get("task_type", "")),
            document_id=UUID(str(document_id)),
        )

    async def _record_execution_event(
        self,
        session: AsyncSession | None,
        *,
        execution_id: UUID,
        event_type: str | ExecutionEventType,
        payload: Any | None = None,
    ) -> None:
        event_type_value = event_type.value if hasattr(event_type, "value") else event_type
        payload_json = serialize_execution_event_payload(payload)

        if session is not None:
            await self._event_repository.create_event(
                session,
                execution_id=execution_id,
                event_type=event_type_value,
                payload_json=payload_json,
            )
            return

        create_event = getattr(self._repository, "create_event", None)
        if create_event is not None:
            await create_event(
                execution_id=execution_id,
                event_type=event_type_value,
                payload=payload_json,
            )

    async def start_execution(
        self,
        user_id: UUID,
        vacancy_id: Optional[UUID] = None,
        profile_id: Optional[UUID] = None,
        pipeline_version: str = "v1.0",
        calibration_version: Optional[str] = None,
        session: AsyncSession | None = None,
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

        execution_state = self._transition_status(PipelineExecutionStatus.CREATED, PipelineExecutionStatus.RUNNING)
        await self._repository.update_execution(
            execution_id=UUID(execution.id),
            status=self._to_repository_status(execution_state),
            started_at=datetime.now(timezone.utc),
            calibration_version=calibration_version,
        )

        await self._record_execution_event(
            session,
            execution_id=UUID(execution.id),
            event_type=ExecutionEventType.EXECUTION_STARTED,
            payload=ExecutionStartedPayload(
                pipeline_version=pipeline_version,
                calibration_version=calibration_version,
            ),
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
        review_required: Optional[bool] = None,
        review_completed: Optional[bool] = None,
        evaluation_duration_ms: Optional[int] = None,
        mutation_duration_ms: Optional[int] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Mark pipeline execution as completed."""
        logger.info("Completing pipeline execution", extra={"execution_id": str(execution_id)})

        execution = await self._repository.get_execution(execution_id)
        current_status = execution.status if execution else None
        self._transition_status(current_status, PipelineExecutionStatus.COMPLETED)

        await self._repository.update_execution(
            execution_id=execution_id,
            status=PipelineStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            artifacts=artifacts,
            metrics=metrics,
            resume_document_id=resume_document_id,
            evaluation_snapshot_id=evaluation_snapshot_id,
            review_id=review_id,
            review_required=review_required,
            review_completed=review_completed,
            evaluation_duration_ms=evaluation_duration_ms,
            mutation_duration_ms=mutation_duration_ms,
        )

        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type=ExecutionEventType.EXECUTION_COMPLETED,
            payload=ExecutionCompletedPayload(
                artifacts_count=len(artifacts) if artifacts else 0,
                metrics_count=len(metrics) if metrics else 0,
            ),
        )

    async def fail_execution(
        self,
        execution_id: UUID,
        error_code: str,
        error_message: str,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Mark pipeline execution as failed."""
        logger.error(
            "Pipeline execution failed",
            extra={"execution_id": str(execution_id), "error_code": error_code},
        )

        execution = await self._repository.get_execution(execution_id)
        current_status = execution.status if execution else None
        self._transition_status(current_status, PipelineExecutionStatus.FAILED)

        await self._repository.update_execution(
            execution_id=execution_id,
            status=PipelineStatus.FAILED,
            failed_at=datetime.now(timezone.utc),
            error_code=error_code,
            error_message=error_message,
            artifacts=artifacts,
            metrics=metrics,
        )

        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type=ExecutionEventType.EXECUTION_FAILED,
            payload=ExecutionFailedPayload(
                error_type=error_code,
                message=error_message,
                error_code=error_code,
                error_message=error_message,
            ),
        )

    async def update_pipeline_status(
        self,
        execution_id: UUID,
        status: PipelineStatus,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Update pipeline execution status to a specific state."""
        logger.info(
            "Updating pipeline status",
            extra={"execution_id": str(execution_id), "status": status.value},
        )

        execution = await self._repository.get_execution(execution_id)
        current_status = execution.status if execution else None
        target_state = self._normalize_status(status)
        if target_state is not None:
            self._transition_status(current_status, target_state)

        await self._repository.update_execution(
            execution_id=execution_id,
            status=status,
            artifacts=artifacts,
            metrics=metrics,
        )

    async def set_profile_loading(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to profile loading."""
        await self.update_pipeline_status(execution_id, PipelineStatus.PROFILE_LOADING, session=session)

    async def set_vacancy_analysis(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to vacancy analysis."""
        await self.update_pipeline_status(execution_id, PipelineStatus.VACANCY_ANALYSIS, session=session)

    async def set_achievement_retrieval(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to achievement retrieval."""
        await self.update_pipeline_status(execution_id, PipelineStatus.ACHIEVEMENT_RETRIEVAL, session=session)

    async def set_coverage_mapping(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to coverage mapping."""
        await self.update_pipeline_status(execution_id, PipelineStatus.COVERAGE_MAPPING, session=session)

    async def set_document_generation(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to document generation."""
        await self.update_pipeline_status(execution_id, PipelineStatus.DOCUMENT_GENERATION, session=session)

    async def set_document_evaluation(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to document evaluation."""
        await self.update_pipeline_status(execution_id, PipelineStatus.DOCUMENT_EVALUATION, session=session)

    async def set_readiness_scoring(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to readiness scoring."""
        await self.update_pipeline_status(execution_id, PipelineStatus.READINESS_SCORING, session=session)
        await self.record_evaluation_completed(execution_id, session=session)

    async def set_review_gate(
        self,
        execution_id: UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """Set pipeline status to review gate."""
        await self.update_pipeline_status(execution_id, PipelineStatus.REVIEW_GATE, session=session)

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
        session: AsyncSession | None = None,
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

        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type="step_started",
            payload=StepStartedPayload(step_name=step_name),
        )

        return step

    async def complete_step(
        self,
        step_id: UUID,
        output_artifact_ids: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
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

        await self._record_execution_event(
            session,
            execution_id=UUID(step.execution_id),
            event_type="step_completed",
            payload=StepCompletedPayload(
                output_artifacts_count=len(output_artifact_ids) if output_artifact_ids else 0,
            ),
        )

    async def fail_step(
        self,
        step_id: UUID,
        error_message: str,
        session: AsyncSession | None = None,
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

        await self._record_execution_event(
            session,
            execution_id=UUID(step.execution_id),
            event_type="step_failed",
            payload=StepFailedPayload(error_message=error_message),
        )

    async def record_evaluation_failed(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        error_details: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Record evaluation failure event."""
        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type="evaluation_failed",
            payload=EvaluationFailedPayload(error_details=error_details),
        )

    async def record_evaluation_completed(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        evaluation_summary: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Record that evaluation has completed."""
        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type=ExecutionEventType.EVALUATION_COMPLETED,
            payload=self._build_evaluation_completed_payload(evaluation_summary),
        )

    async def record_review_required(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        review_reason: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Record that manual review is required."""
        execution = await self._repository.get_execution(execution_id)
        current_status = execution.status if execution else None
        self._transition_status(current_status, PipelineExecutionStatus.REVIEW_REQUIRED)

        await self._repository.update_execution(
            execution_id=execution_id,
            review_required=True,
            status=PipelineStatus.REVIEW_GATE,
            error_message=review_reason,
        )

        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type="review_required",
            payload=ReviewRequiredPayload(review_reason=review_reason),
        )

    async def record_review_completed(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        review_summary: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Record that manual review is completed."""
        await self._repository.update_execution(
            execution_id=execution_id,
            review_completed=True,
        )

        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type=ExecutionEventType.REVIEW_COMPLETED,
            payload=ReviewCompletedPayload(review_summary=review_summary),
        )

    async def record_recommendation_applied(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        recommendation_data: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Record that a recommendation was applied."""
        await self._record_execution_event(
            session,
            execution_id=execution_id,
            event_type=ExecutionEventType.RECOMMENDATION_APPLIED,
            payload=self._build_recommendation_applied_payload(recommendation_data),
        )

    async def record_recommendation_generated(
        self,
        execution_id: UUID,
        step_id: Optional[UUID] = None,
        recommendation_data: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Backward-compatible alias for recommendation_applied."""
        await self.record_recommendation_applied(
            execution_id=execution_id,
            step_id=step_id,
            recommendation_data=recommendation_data,
            session=session,
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
