# app\repositories\pipeline_repository.py

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import enrich_execution_event_payload
from app.domain.pipeline_models import (
    CareerCopilotRun,
    PipelineExecutionStep,
    PipelineEvent,
    PipelineStatus,
    PipelineEventType,
    EventSeverity,
    PipelineExecutionSummary,
    StepStatus,
)
from app.models.entities import (
    PipelineExecution as PipelineExecutionModel,
    PipelineExecutionStep as PipelineExecutionStepModel,
    PipelineEvent as PipelineEventModel,
)


class PipelineRepository(Protocol):
    """Repository for managing pipeline execution records."""

    @abstractmethod
    async def create_execution(
        self,
        user_id: UUID,
        execution_id: UUID | None = None,
        document_id: Optional[UUID] = None,
        vacancy_id: Optional[UUID] = None,
        profile_id: Optional[UUID] = None,
        pipeline_version: str = "v1.0",
        calibration_version: str | None = None,
        idempotency_key: str | None = None,
        retry_count: int = 0,
        failed_step: str | None = None,
        last_error: str | None = None,
        parent_execution_id: UUID | None = None,
        lineage_kind: str | None = None,
        lineage_reason: str | None = None,
        lineage_metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> CareerCopilotRun:
        """Create a new pipeline execution record."""
        ...

    @abstractmethod
    async def get_execution_by_idempotency_key(
        self,
        user_id: UUID,
        document_id: UUID,
        vacancy_id: UUID,
        idempotency_key: str,
    ) -> Optional[CareerCopilotRun]:
        """Find an existing execution for an idempotent request."""
        ...

    @abstractmethod
    async def get_execution(self, execution_id: UUID) -> Optional[CareerCopilotRun]:
        """Retrieve a pipeline execution by ID."""
        ...

    async def get_execution_with_steps_and_events(self, execution_id: UUID) -> Optional[PipelineExecutionSummary]:
        """Retrieve execution with all steps and events."""
        ...

    @abstractmethod
    async def update_execution(
        self,
        execution_id: UUID,
        status: Optional[PipelineStatus] = None,
        review_required: Optional[bool] = None,
        review_completed: Optional[bool] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        calibration_version: Optional[str] = None,
        execution_duration_ms: Optional[int] = None,
        evaluation_duration_ms: Optional[int] = None,
        mutation_duration_ms: Optional[int] = None,
        retry_count: Optional[int] = None,
        failed_step: Optional[str] = None,
        last_error: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        resume_document_id: Optional[UUID] = None,
        evaluation_snapshot_id: Optional[UUID] = None,
        review_id: Optional[UUID] = None,
    ) -> None:
        """Update execution metadata."""
        ...

    @abstractmethod
    async def create_step(
        self,
        execution_id: UUID,
        step_name: str,
        input_artifact_ids: Optional[list[str]] = None,
    ) -> PipelineExecutionStep:
        """Create a new execution step."""
        ...

    @abstractmethod
    async def update_step(
        self,
        step_id: UUID,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        output_artifact_ids: Optional[list[str]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update step status and metadata."""
        ...

    @abstractmethod
    async def get_step(self, step_id: UUID) -> Optional[PipelineExecutionStep]:
        """Get a pipeline execution step by ID."""
        ...

    @abstractmethod
    async def create_event(
        self,
        execution_id: UUID,
        event_type: PipelineEventType,
        payload: Optional[dict[str, Any]] = None,
        step_id: Optional[UUID] = None,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> PipelineEvent:
        """Record a pipeline event."""
        ...

    @abstractmethod
    async def get_executions_for_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a user."""
        ...

    @abstractmethod
    async def get_executions_for_vacancy(
        self,
        vacancy_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a vacancy."""
        ...

    @abstractmethod
    async def get_child_executions(self, parent_execution_id: UUID) -> list[CareerCopilotRun]:
        """Get child executions for a parent execution."""
        ...


class SQLAlchemyAsyncPipelineRepository:
    """SQLAlchemy async implementation for pipeline execution tracking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_execution(
        self,
        user_id: UUID,
        execution_id: UUID | None = None,
        document_id: Optional[UUID] = None,
        vacancy_id: Optional[UUID] = None,
        profile_id: Optional[UUID] = None,
        pipeline_version: str = "v1.0",
        calibration_version: str | None = None,
        idempotency_key: str | None = None,
        retry_count: int = 0,
        failed_step: str | None = None,
        last_error: str | None = None,
        parent_execution_id: UUID | None = None,
        lineage_kind: str | None = None,
        lineage_reason: str | None = None,
        lineage_metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> CareerCopilotRun:
        """Create a new pipeline execution record."""
        execution = PipelineExecutionModel(
            id=execution_id or uuid4(),
            user_id=user_id,
            document_id=document_id,
            vacancy_id=vacancy_id,
            profile_id=profile_id,
            pipeline_version=pipeline_version,
            calibration_version=calibration_version,
            idempotency_key=idempotency_key,
            retry_count=retry_count,
            failed_step=failed_step,
            last_error=last_error,
            parent_execution_id=parent_execution_id,
            lineage_kind=lineage_kind,
            lineage_reason=lineage_reason,
            lineage_metadata_json=lineage_metadata or {},
            status="pending",
        )
        self._session.add(execution)
        await self._session.flush()

        # Record pipeline_started event
        event = PipelineEventModel(
            execution_id=execution.id,
            event_type="pipeline_started",
            severity="info",
            payload_json=enrich_execution_event_payload(
                execution.id,
                {"pipeline_version": pipeline_version},
            ),
        )
        self._session.add(event)
        if commit:
            await self._session.commit()

        return CareerCopilotRun(
            id=str(execution.id),
            user_id=str(execution.user_id),
            document_id=str(execution.document_id) if execution.document_id else None,
            vacancy_id=str(execution.vacancy_id) if execution.vacancy_id else None,
            profile_id=str(execution.profile_id) if execution.profile_id else None,
            idempotency_key=execution.idempotency_key,
            parent_execution_id=str(execution.parent_execution_id) if execution.parent_execution_id else None,
            lineage_kind=execution.lineage_kind,
            lineage_reason=execution.lineage_reason,
            lineage_metadata=execution.lineage_metadata_json,
            status=PipelineStatus.PENDING,
            review_required=execution.review_required,
            review_completed=execution.review_completed,
            failed_at=execution.failed_at,
            pipeline_version=pipeline_version,
            calibration_version=calibration_version,
            execution_duration_ms=execution.execution_duration_ms,
            evaluation_duration_ms=execution.evaluation_duration_ms,
            mutation_duration_ms=execution.mutation_duration_ms,
            retry_count=execution.retry_count,
            failed_step=execution.failed_step,
            last_error=execution.last_error,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )

    async def get_execution(self, execution_id: UUID) -> Optional[CareerCopilotRun]:
        """Retrieve a pipeline execution by ID."""
        stmt = select(PipelineExecutionModel).where(PipelineExecutionModel.id == execution_id)
        result = await self._session.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            return None

        return self._map_to_career_copilot_run(execution)

    async def get_execution_by_idempotency_key(
        self,
        user_id: UUID,
        document_id: UUID,
        vacancy_id: UUID,
        idempotency_key: str,
    ) -> Optional[CareerCopilotRun]:
        stmt = select(PipelineExecutionModel).where(
            PipelineExecutionModel.user_id == user_id,
            PipelineExecutionModel.document_id == document_id,
            PipelineExecutionModel.vacancy_id == vacancy_id,
            PipelineExecutionModel.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        execution = result.scalar_one_or_none()
        if not execution:
            return None
        return self._map_to_career_copilot_run(execution)

    async def get_execution_with_steps_and_events(self, execution_id: UUID) -> Optional[PipelineExecutionSummary]:
        """Retrieve execution with all steps and events."""
        stmt = select(PipelineExecutionModel).where(PipelineExecutionModel.id == execution_id)
        result = await self._session.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            return None

        # Load steps
        steps_stmt = select(PipelineExecutionStepModel).where(
            PipelineExecutionStepModel.execution_id == execution_id
        ).order_by(PipelineExecutionStepModel.started_at.asc())
        steps_result = await self._session.execute(steps_stmt)
        steps = [self._map_to_step(step) for step in steps_result.scalars().all()]

        # Load events
        events_stmt = select(PipelineEventModel).where(
            PipelineEventModel.execution_id == execution_id
        ).order_by(PipelineEventModel.created_at.asc())
        events_result = await self._session.execute(events_stmt)
        events = [self._map_to_event(event) for event in events_result.scalars().all()]

        return PipelineExecutionSummary(
            execution=self._map_to_career_copilot_run(execution),
            steps=steps,
            events=events,
        )

    async def update_execution(
        self,
        execution_id: UUID,
        status: Optional[PipelineStatus] = None,
        review_required: Optional[bool] = None,
        review_completed: Optional[bool] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        calibration_version: Optional[str] = None,
        execution_duration_ms: Optional[int] = None,
        evaluation_duration_ms: Optional[int] = None,
        mutation_duration_ms: Optional[int] = None,
        retry_count: Optional[int] = None,
        failed_step: Optional[str] = None,
        last_error: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        resume_document_id: Optional[UUID] = None,
        evaluation_snapshot_id: Optional[UUID] = None,
        review_id: Optional[UUID] = None,
        commit: bool = True,
    ) -> None:
        """Update execution metadata."""
        stmt = select(PipelineExecutionModel).where(PipelineExecutionModel.id == execution_id)
        result = await self._session.execute(stmt)
        execution = result.scalar_one_or_none()

        if not execution:
            return

        if status is not None:
            execution.status = status.value
        if review_required is not None:
            execution.review_required = review_required
        if review_completed is not None:
            execution.review_completed = review_completed
        if started_at is not None:
            execution.started_at = started_at
        if completed_at is not None:
            execution.completed_at = completed_at
            if execution.started_at:
                execution.execution_duration_ms = int(
                    (completed_at - execution.started_at).total_seconds() * 1000
                )
                execution.duration_ms = execution.execution_duration_ms
        if failed_at is not None:
            execution.failed_at = failed_at
        if calibration_version is not None:
            execution.calibration_version = calibration_version
        if execution_duration_ms is not None:
            execution.execution_duration_ms = execution_duration_ms
            execution.duration_ms = execution_duration_ms
        if evaluation_duration_ms is not None:
            execution.evaluation_duration_ms = evaluation_duration_ms
        if mutation_duration_ms is not None:
            execution.mutation_duration_ms = mutation_duration_ms
        if retry_count is not None:
            execution.retry_count = retry_count
        if failed_step is not None:
            execution.failed_step = failed_step
        if last_error is not None:
            execution.last_error = last_error
        if error_code is not None:
            execution.error_code = error_code
        if error_message is not None:
            execution.error_message = error_message
        if artifacts is not None:
            execution.artifacts_json = artifacts
        if metrics is not None:
            execution.metrics_json = metrics
        if resume_document_id is not None:
            execution.resume_document_id = resume_document_id
        if evaluation_snapshot_id is not None:
            execution.evaluation_snapshot_id = evaluation_snapshot_id
        if review_id is not None:
            execution.review_id = review_id

        if commit:
            await self._session.commit()

    async def create_step(
        self,
        execution_id: UUID,
        step_name: str,
        input_artifact_ids: Optional[list[str]] = None,
    ) -> PipelineExecutionStep:
        """Create a new execution step."""
        step = PipelineExecutionStepModel(
            execution_id=execution_id,
            step_name=step_name,
            status="pending",
            input_artifact_ids=input_artifact_ids or [],
        )
        self._session.add(step)
        await self._session.flush()

        return PipelineExecutionStep(
            id=str(step.id),
            execution_id=str(step.execution_id),
            step_name=step.step_name,
            status=StepStatus.PENDING,
            input_artifact_ids=step.input_artifact_ids,
        )

    async def get_step(self, step_id: UUID) -> Optional[PipelineExecutionStep]:
        """Get a pipeline execution step by ID."""
        stmt = select(PipelineExecutionStepModel).where(PipelineExecutionStepModel.id == step_id)
        result = await self._session.execute(stmt)
        step = result.scalar_one_or_none()

        if not step:
            return None

        return self._map_to_step(step)

    async def update_step(
        self,
        step_id: UUID,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        output_artifact_ids: Optional[list[str]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        commit: bool = True,
    ) -> None:
        """Update step status and metadata."""
        stmt = select(PipelineExecutionStepModel).where(PipelineExecutionStepModel.id == step_id)
        result = await self._session.execute(stmt)
        step = result.scalar_one_or_none()

        if not step:
            return

        if status is not None:
            step.status = status
        if started_at is not None:
            step.started_at = started_at
        if completed_at is not None:
            step.completed_at = completed_at
        if duration_ms is not None:
            step.duration_ms = duration_ms
        if output_artifact_ids is not None:
            step.output_artifact_ids = output_artifact_ids
        if error_message is not None:
            step.error_message = error_message
        if metadata is not None:
            step.metadata_json = metadata

        if commit:
            await self._session.commit()

    async def create_event(
        self,
        execution_id: UUID,
        event_type: PipelineEventType,
        payload: Optional[dict[str, Any]] = None,
        step_id: Optional[UUID] = None,
        severity: EventSeverity = EventSeverity.INFO,
        commit: bool = True,
    ) -> PipelineEvent:
        """Record a pipeline event."""
        event = PipelineEventModel(
            execution_id=execution_id,
            event_type=event_type.value,
            step_id=step_id,
            payload_json=enrich_execution_event_payload(execution_id, payload),
            severity=severity.value,
        )
        self._session.add(event)
        if commit:
            await self._session.commit()

        return PipelineEvent(
            id=str(event.id),
            execution_id=str(event.execution_id),
            event_type=event_type,
            step_id=str(event.step_id) if event.step_id else None,
            payload=event.payload_json,
            severity=severity,
            created_at=event.created_at,
        )

    async def get_executions_for_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a user."""
        stmt = select(PipelineExecutionModel).where(PipelineExecutionModel.user_id == user_id)

        if status:
            stmt = stmt.where(PipelineExecutionModel.status == status)

        stmt = stmt.order_by(PipelineExecutionModel.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        executions = result.scalars().all()

        return [self._map_to_career_copilot_run(exec) for exec in executions]

    async def get_executions_for_vacancy(
        self,
        vacancy_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a vacancy."""
        stmt = (
            select(PipelineExecutionModel)
            .where(PipelineExecutionModel.vacancy_id == vacancy_id)
            .order_by(PipelineExecutionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        executions = result.scalars().all()

        return [self._map_to_career_copilot_run(exec) for exec in executions]

    async def get_child_executions(self, parent_execution_id: UUID) -> list[CareerCopilotRun]:
        stmt = (
            select(PipelineExecutionModel)
            .where(PipelineExecutionModel.parent_execution_id == parent_execution_id)
            .order_by(PipelineExecutionModel.created_at.asc())
        )

        result = await self._session.execute(stmt)
        executions = result.scalars().all()

        return [self._map_to_career_copilot_run(exec) for exec in executions]

    async def get_stuck_executions(
        self,
        *,
        older_than: datetime,
        limit: int = 100,
    ) -> list[CareerCopilotRun]:
        running_statuses = [
            PipelineStatus.RUNNING.value,
            PipelineStatus.PROFILE_LOADING.value,
            PipelineStatus.VACANCY_ANALYSIS.value,
            PipelineStatus.ACHIEVEMENT_RETRIEVAL.value,
            PipelineStatus.COVERAGE_MAPPING.value,
            PipelineStatus.DOCUMENT_GENERATION.value,
            PipelineStatus.DOCUMENT_EVALUATION.value,
            PipelineStatus.READINESS_SCORING.value,
        ]

        stmt = (
            select(PipelineExecutionModel)
            .where(PipelineExecutionModel.status.in_(running_statuses))
            .where(PipelineExecutionModel.started_at.isnot(None))
            .where(PipelineExecutionModel.started_at < older_than)
            .order_by(PipelineExecutionModel.started_at.asc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return [
            self._map_to_career_copilot_run(execution)
            for execution in result.scalars().all()
        ]

    @staticmethod
    def _map_to_career_copilot_run(execution: PipelineExecutionModel) -> CareerCopilotRun:
        """Map SQLAlchemy model to domain model."""
        status = PipelineStatus(execution.status) if execution.status else PipelineStatus.PENDING

        return CareerCopilotRun(
            id=str(execution.id),
            user_id=str(execution.user_id),
            document_id=str(execution.document_id) if execution.document_id else None,
            vacancy_id=str(execution.vacancy_id) if execution.vacancy_id else None,
            profile_id=str(execution.profile_id) if execution.profile_id else None,
            resume_document_id=str(execution.resume_document_id) if execution.resume_document_id else None,
            evaluation_snapshot_id=str(execution.evaluation_snapshot_id) if execution.evaluation_snapshot_id else None,
            review_id=str(execution.review_id) if execution.review_id else None,
            idempotency_key=execution.idempotency_key,
            parent_execution_id=str(execution.parent_execution_id) if execution.parent_execution_id else None,
            lineage_kind=execution.lineage_kind,
            lineage_reason=execution.lineage_reason,
            lineage_metadata=execution.lineage_metadata_json,
            status=status,
            review_required=execution.review_required,
            review_completed=execution.review_completed,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            failed_at=execution.failed_at,
            pipeline_version=execution.pipeline_version or "v1.0",
            calibration_version=execution.calibration_version,
            execution_duration_ms=execution.execution_duration_ms,
            evaluation_duration_ms=execution.evaluation_duration_ms,
            mutation_duration_ms=execution.mutation_duration_ms,
            retry_count=execution.retry_count,
            failed_step=execution.failed_step,
            last_error=execution.last_error,
            error_code=execution.error_code,
            error_message=execution.error_message,
            artifacts=execution.artifacts_json,
            metrics=execution.metrics_json,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )

    @staticmethod
    def _map_to_step(step: PipelineExecutionStepModel) -> PipelineExecutionStep:
        """Map SQLAlchemy model to domain model."""
        status = StepStatus(step.status) if step.status else StepStatus.PENDING

        return PipelineExecutionStep(
            id=str(step.id),
            execution_id=str(step.execution_id),
            step_name=step.step_name,
            status=status,
            started_at=step.started_at,
            completed_at=step.completed_at,
            duration_ms=step.duration_ms,
            input_artifact_ids=step.input_artifact_ids,
            output_artifact_ids=step.output_artifact_ids,
            error_message=step.error_message,
            metadata=step.metadata_json,
        )

    @staticmethod
    def _map_to_event(event: PipelineEventModel) -> PipelineEvent:
        """Map SQLAlchemy model to domain model."""
        event_type = PipelineEventType(event.event_type)
        severity = EventSeverity(event.severity)

        return PipelineEvent(
            id=str(event.id),
            execution_id=str(event.execution_id),
            event_type=event_type,
            step_id=str(event.step_id) if event.step_id else None,
            payload=event.payload_json,
            severity=severity,
            created_at=event.created_at,
        )


class InMemoryPipelineRepository:
    """In-memory implementation of PipelineRepository for testing."""

    def __init__(self):
        self._executions: dict[str, CareerCopilotRun] = {}
        self._steps: dict[str, list[PipelineExecutionStep]] = {}
        self._events: dict[str, list[PipelineEvent]] = {}

    async def create_execution(
        self,
        user_id: UUID,
        execution_id: UUID | None = None,
        document_id: Optional[UUID] = None,
        vacancy_id: Optional[UUID] = None,
        profile_id: Optional[UUID] = None,
        pipeline_version: str = "v1.0",
        calibration_version: str | None = None,
        idempotency_key: str | None = None,
        retry_count: int = 0,
        failed_step: str | None = None,
        last_error: str | None = None,
        parent_execution_id: UUID | None = None,
        lineage_kind: str | None = None,
        lineage_reason: str | None = None,
        lineage_metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> CareerCopilotRun:
        """Create a new pipeline execution record."""
        execution_id = str(execution_id or uuid4())
        execution = CareerCopilotRun(
            id=execution_id,
            user_id=str(user_id),
            document_id=str(document_id) if document_id else None,
            vacancy_id=str(vacancy_id) if vacancy_id else None,
            profile_id=str(profile_id) if profile_id else None,
            pipeline_version=pipeline_version,
            calibration_version=calibration_version,
            idempotency_key=idempotency_key,
            parent_execution_id=str(parent_execution_id) if parent_execution_id else None,
            lineage_kind=lineage_kind,
            lineage_reason=lineage_reason,
            lineage_metadata=lineage_metadata or {},
            status=PipelineStatus.PENDING,
            failed_at=None,
            retry_count=retry_count,
            failed_step=failed_step,
            last_error=last_error,
        )
        self._executions[execution_id] = execution
        self._steps[execution_id] = []
        self._events[execution_id] = []
        return execution

    async def get_execution_by_idempotency_key(
        self,
        user_id: UUID,
        document_id: UUID,
        vacancy_id: UUID,
        idempotency_key: str,
    ) -> Optional[CareerCopilotRun]:
        for execution in self._executions.values():
            if (
                execution.user_id == str(user_id)
                and execution.document_id == str(document_id)
                and execution.vacancy_id == str(vacancy_id)
                and execution.idempotency_key == idempotency_key
            ):
                return execution
        return None

    async def get_execution(self, execution_id: UUID) -> Optional[CareerCopilotRun]:
        """Retrieve a pipeline execution by ID."""
        return self._executions.get(str(execution_id))

    async def get_execution_with_steps_and_events(self, execution_id: UUID) -> Optional[PipelineExecutionSummary]:
        """Retrieve execution with all steps and events."""
        execution = self._executions.get(str(execution_id))
        if not execution:
            return None

        steps = self._steps.get(str(execution_id), [])
        events = self._events.get(str(execution_id), [])

        return PipelineExecutionSummary(
            execution=execution,
            steps=steps,
            events=events,
        )

    async def update_execution(
        self,
        execution_id: UUID,
        status: Optional[PipelineStatus] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        retry_count: Optional[int] = None,
        failed_step: Optional[str] = None,
        last_error: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        artifacts: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        resume_document_id: Optional[UUID] = None,
        evaluation_snapshot_id: Optional[UUID] = None,
        review_id: Optional[UUID] = None,
        commit: bool = True,
    ) -> None:
        """Update pipeline execution."""
        execution = self._executions.get(str(execution_id))
        if not execution:
            return

        if status is not None:
            execution.status = status
        if started_at is not None:
            execution.started_at = started_at
        if completed_at is not None:
            execution.completed_at = completed_at
        if failed_at is not None:
            execution.failed_at = failed_at
        if retry_count is not None:
            execution.retry_count = retry_count
        if failed_step is not None:
            execution.failed_step = failed_step
        if last_error is not None:
            execution.last_error = last_error
        if error_code is not None:
            execution.error_code = error_code
        if error_message is not None:
            execution.error_message = error_message
        if artifacts is not None:
            execution.artifacts = artifacts
        if metrics is not None:
            execution.metrics = metrics
        if resume_document_id is not None:
            execution.resume_document_id = str(resume_document_id)
        if evaluation_snapshot_id is not None:
            execution.evaluation_snapshot_id = str(evaluation_snapshot_id)
        if review_id is not None:
            execution.review_id = str(review_id)

    async def create_step(
        self,
        execution_id: UUID,
        step_name: str,
        input_artifact_ids: Optional[list[str]] = None,
    ) -> PipelineExecutionStep:
        """Create a new pipeline step."""
        step_id = str(uuid4())
        step = PipelineExecutionStep(
            id=step_id,
            execution_id=str(execution_id),
            step_name=step_name,
            input_artifact_ids=input_artifact_ids or [],
        )
        self._steps[str(execution_id)].append(step)
        return step

    async def update_step(
        self,
        step_id: UUID,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        output_artifact_ids: Optional[list[str]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        commit: bool = True,
    ) -> None:
        """Update step status and metadata."""
        for execution_steps in self._steps.values():
            for step in execution_steps:
                if step.id == str(step_id):
                    if status is not None:
                        step.status = StepStatus(status)
                    if started_at is not None:
                        step.started_at = started_at
                    if completed_at is not None:
                        step.completed_at = completed_at
                    if duration_ms is not None:
                        step.duration_ms = duration_ms
                    if output_artifact_ids is not None:
                        step.output_artifact_ids = output_artifact_ids
                    if error_message is not None:
                        step.error_message = error_message
                    if metadata is not None:
                        step.metadata = metadata
                    return

    async def create_event(
        self,
        execution_id: UUID,
        event_type: PipelineEventType,
        payload: Optional[dict[str, Any]] = None,
        step_id: Optional[UUID] = None,
        severity: EventSeverity = EventSeverity.INFO,
        commit: bool = True,
    ) -> PipelineEvent:
        """Record a pipeline event."""
        event_id = str(uuid4())
        event = PipelineEvent(
            id=event_id,
            execution_id=str(execution_id),
            event_type=event_type,
            step_id=str(step_id) if step_id else None,
            payload=enrich_execution_event_payload(execution_id, payload),
            severity=severity,
        )
        self._events[str(execution_id)].append(event)
        return event

    async def get_executions_for_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a user."""
        executions = [
            exec for exec in self._executions.values()
            if exec.user_id == str(user_id)
        ]

        if status:
            executions = [exec for exec in executions if exec.status.value == status]

        return executions[offset:offset + limit]

    async def get_executions_for_vacancy(
        self,
        vacancy_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CareerCopilotRun]:
        """Get pipeline executions for a vacancy."""
        executions = [
            exec for exec in self._executions.values()
            if exec.vacancy_id == str(vacancy_id)
        ]
        return executions[offset:offset + limit]

    async def get_child_executions(self, parent_execution_id: UUID) -> list[CareerCopilotRun]:
        executions = [
            exec for exec in self._executions.values()
            if exec.parent_execution_id == str(parent_execution_id)
        ]
        executions.sort(key=lambda execution: execution.created_at)
        return executions

    async def get_stuck_executions(
        self,
        *,
        older_than: datetime,
        limit: int = 100,
    ) -> list[CareerCopilotRun]:
        running_statuses = {
            PipelineStatus.RUNNING,
            PipelineStatus.PROFILE_LOADING,
            PipelineStatus.VACANCY_ANALYSIS,
            PipelineStatus.ACHIEVEMENT_RETRIEVAL,
            PipelineStatus.COVERAGE_MAPPING,
            PipelineStatus.DOCUMENT_GENERATION,
            PipelineStatus.DOCUMENT_EVALUATION,
            PipelineStatus.READINESS_SCORING,
        }
        executions = [
            execution for execution in self._executions.values()
            if execution.status in running_statuses
            and execution.started_at is not None
            and execution.started_at < older_than
        ]
        executions.sort(key=lambda execution: execution.started_at or datetime.max.replace(tzinfo=timezone.utc))
        return executions[:limit]


    def save_run(self, run: CareerCopilotRun) -> None:
        """Save a pipeline run (for testing compatibility)."""
        self._executions[str(run.id)] = run
        if str(run.id) not in self._steps:
            self._steps[str(run.id)] = []
        if str(run.id) not in self._events:
            self._events[str(run.id)] = []

    def get_run(self, run_id: str) -> Optional[CareerCopilotRun]:
        """Get a pipeline run by ID (for testing compatibility)."""
        return self._executions.get(run_id)

    def get_runs_for_user(self, user_id: str, limit: int = 20) -> list[CareerCopilotRun]:
        """Get pipeline runs for a user (for testing compatibility)."""
        executions = [
            exec for exec in self._executions.values()
            if exec.user_id == user_id
        ]
        # Sort by started_at descending (most recent first)
        min_aware = datetime.min.replace(tzinfo=timezone.utc)
        executions.sort(key=lambda x: x.started_at or min_aware, reverse=True)
        return executions[:limit]

    def get_runs_for_vacancy(self, vacancy_id: str) -> list[CareerCopilotRun]:
        """Get pipeline runs for a vacancy (for testing compatibility)."""
        executions = [
            exec for exec in self._executions.values()
            if exec.vacancy_id == vacancy_id
        ]
        return executions
