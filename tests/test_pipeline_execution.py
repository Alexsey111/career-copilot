from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import UUID, uuid4

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
    ExecutionStartedPayload,
    serialize_execution_event_payload,
)
from app.domain.pipeline_execution_status import PipelineExecutionStatus
from app.repositories.pipeline_execution_repository import ExecutionRuntimeAggregate, PipelineExecutionRepository
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.services.career_pipeline_orchestrator import CareerPipelineOrchestrator
from app.services.execution_observability_service import ExecutionObservabilityService
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.stuck_execution_service import StuckExecutionService


class TestPipelineDomainModels:
    """Tests for pipeline domain models."""

    def test_career_copilot_run_creation(self):
        """Test creating a pipeline run."""
        user_id = str(uuid4())
        vacancy_id = str(uuid4())

        run = CareerCopilotRun(
            id=str(uuid4()),
            user_id=user_id,
            vacancy_id=vacancy_id,
            profile_id=str(uuid4()),
            pipeline_version="v1.0",
            status=PipelineStatus.PENDING,
        )

        assert run.user_id == user_id
        assert run.vacancy_id == vacancy_id
        assert run.status == PipelineStatus.PENDING
        assert run.pipeline_version == "v1.0"
        assert run.artifacts == {}
        assert run.metrics == {}

    def test_career_copilot_run_with_artifacts(self):
        """Test pipeline run with artifacts and metrics."""
        run = CareerCopilotRun(
            id=str(uuid4()),
            user_id=str(uuid4()),
            vacancy_id=str(uuid4()),
            profile_id=str(uuid4()),
            status=PipelineStatus.COMPLETED,
            artifacts={"resume": "doc_123", "cover_letter": "doc_456"},
            metrics={"match_score": 0.85, "quality_score": 0.92},
        )

        assert run.artifacts["resume"] == "doc_123"
        assert run.metrics["match_score"] == 0.85

    def test_pipeline_execution_step_creation(self):
        """Test creating a pipeline execution step."""
        step = PipelineExecutionStep(
            id=str(uuid4()),
            execution_id=str(uuid4()),
            step_name="extract_features",
            status=StepStatus.RUNNING,
            input_artifact_ids=["input_1", "input_2"],
        )

        assert step.step_name == "extract_features"
        assert step.status == StepStatus.RUNNING
        assert len(step.input_artifact_ids) == 2

    def test_pipeline_event_creation(self):
        """Test creating a pipeline event."""
        event = PipelineEvent(
            id=str(uuid4()),
            execution_id=str(uuid4()),
            event_type=PipelineEventType.PIPELINE_STARTED,
            payload={"version": "v1.0"},
            severity=EventSeverity.INFO,
        )

        assert event.event_type == PipelineEventType.PIPELINE_STARTED
        assert event.severity == EventSeverity.INFO
        assert event.payload["version"] == "v1.0"

    def test_pipeline_execution_summary(self):
        """Test pipeline execution summary aggregation."""
        execution = CareerCopilotRun(
            id=str(uuid4()),
            user_id=str(uuid4()),
            vacancy_id=str(uuid4()),
            profile_id=str(uuid4()),
            status=PipelineStatus.RUNNING,
            started_at=datetime.now(),
        )

        step1 = PipelineExecutionStep(
            id=str(uuid4()),
            execution_id=execution.id,
            step_name="step1",
            status=StepStatus.COMPLETED,
        )
        step2 = PipelineExecutionStep(
            id=str(uuid4()),
            execution_id=execution.id,
            step_name="step2",
            status=StepStatus.FAILED,
        )

        summary = PipelineExecutionSummary(
            execution=execution,
            steps=[step1, step2],
        )

        assert len(summary.steps) == 2
        assert len(summary.completed_steps) == 1
        assert len(summary.failed_steps) == 1


class TestPipelineRepository:
    """Tests for pipeline repository."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        # add() is a synchronous method in SQLAlchemy
        session.add = MagicMock()
        return session

    @pytest.fixture
    def repository(self, mock_session):
        """Create repository with mock session."""
        return SQLAlchemyAsyncPipelineRepository(session=mock_session)

    @pytest.mark.asyncio
    async def test_create_execution(self, repository, mock_session):
        """Test creating a pipeline execution."""
        user_id = uuid4()

        # Mock the execution model
        mock_execution = MagicMock()
        mock_execution.id = uuid4()
        mock_execution.user_id = user_id
        mock_execution.vacancy_id = None
        mock_execution.profile_id = None
        mock_execution.status = "pending"
        mock_execution.pipeline_version = "v1.0"
        mock_execution.calibration_version = None
        mock_execution.started_at = None
        mock_execution.completed_at = None
        mock_execution.failed_at = None
        mock_execution.resume_document_id = None
        mock_execution.evaluation_snapshot_id = None
        mock_execution.review_id = None
        mock_execution.error_code = None
        mock_execution.error_message = None
        mock_execution.artifacts_json = {}
        mock_execution.metrics_json = {}
        mock_execution.created_at = datetime.now()
        mock_execution.updated_at = datetime.now()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_session.execute.return_value = mock_result

        execution = await repository.create_execution(
            user_id=user_id,
            pipeline_version="v1.0",
        )

        assert execution.user_id == str(user_id)
        assert execution.status == PipelineStatus.PENDING
        assert execution.pipeline_version == "v1.0"

    @pytest.mark.asyncio
    async def test_create_execution_persists_lineage_fields(self, repository, mock_session):
        user_id = uuid4()
        parent_execution_id = uuid4()

        execution = await repository.create_execution(
            user_id=user_id,
            pipeline_version="v1.0",
            parent_execution_id=parent_execution_id,
            lineage_kind="resume",
            lineage_reason="Dependency outage resolved",
            lineage_metadata={"resume_from_step": "mutation"},
        )

        persisted_execution = mock_session.add.call_args_list[0].args[0]
        assert persisted_execution.parent_execution_id == parent_execution_id
        assert persisted_execution.lineage_kind == "resume"
        assert persisted_execution.lineage_reason == "Dependency outage resolved"
        assert persisted_execution.lineage_metadata_json == {"resume_from_step": "mutation"}
        assert execution.parent_execution_id == str(parent_execution_id)
        assert execution.lineage_kind == "resume"
        assert execution.lineage_reason == "Dependency outage resolved"
        assert execution.lineage_metadata == {"resume_from_step": "mutation"}

    @pytest.mark.asyncio
    async def test_get_phase_runtime_aggregates(self, mock_session):
        repository = PipelineExecutionRepository()

        mock_row = MagicMock()
        mock_row.step_name = "mutation"
        mock_row.total_count = 10
        mock_row.completed_count = 8
        mock_row.failed_count = 2
        mock_row.avg_duration_ms = 1500.0
        mock_row.max_duration_ms = 2500.0
        mock_row.retry_count = 3
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        aggregates = await repository.get_phase_runtime_aggregates(mock_session)

        assert len(aggregates) == 1
        assert aggregates[0].step_name == "mutation"
        assert aggregates[0].total_count == 10
        assert aggregates[0].completed_count == 8
        assert aggregates[0].failed_count == 2
        assert aggregates[0].avg_duration_ms == 1500.0
        assert aggregates[0].max_duration_ms == 2500.0
        assert aggregates[0].retry_count == 3


class TestPipelineExecutionService:
    """Tests for pipeline execution service."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        return MagicMock(spec=SQLAlchemyAsyncPipelineRepository)

    @pytest.fixture
    def service(self, mock_repository):
        """Create service with mock repository."""
        return PipelineExecutionService(repository=mock_repository)

    @pytest.mark.asyncio
    async def test_start_execution(self, service, mock_repository):
        """Test starting a pipeline execution."""
        user_id = uuid4()
        vacancy_id = uuid4()

        mock_execution = CareerCopilotRun(
            id=str(uuid4()),
            user_id=str(user_id),
            vacancy_id=str(vacancy_id),
            profile_id=None,
            status=PipelineStatus.RUNNING,
        )

        mock_repository.create_execution = AsyncMock(return_value=mock_execution)
        mock_repository.update_execution = AsyncMock()

        execution = await service.start_execution(
            user_id=user_id,
            vacancy_id=vacancy_id,
            pipeline_version="v1.0",
            calibration_version="v2.0",
        )

        assert execution.status == PipelineStatus.RUNNING
        mock_repository.create_execution.assert_called_once()
        mock_repository.update_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_execution_returns_existing_for_same_idempotency_key(
        self,
        service,
        mock_repository,
    ):
        user_id = uuid4()
        document_id = uuid4()
        vacancy_id = uuid4()
        existing_execution = CareerCopilotRun(
            id=str(uuid4()),
            user_id=str(user_id),
            vacancy_id=str(vacancy_id),
            profile_id=None,
            document_id=str(document_id),
            idempotency_key="idem-123",
            status=PipelineStatus.COMPLETED,
        )

        mock_repository.get_execution_by_idempotency_key = AsyncMock(return_value=existing_execution)
        mock_repository.create_execution = AsyncMock()
        mock_repository.update_execution = AsyncMock()

        execution = await service.start_execution(
            user_id=user_id,
            document_id=document_id,
            vacancy_id=vacancy_id,
            pipeline_version="v1.0",
            idempotency_key="idem-123",
        )

        assert execution.id == existing_execution.id
        mock_repository.get_execution_by_idempotency_key.assert_called_once_with(
            user_id,
            document_id,
            vacancy_id,
            "idem-123",
        )
        mock_repository.create_execution.assert_not_called()
        mock_repository.update_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_execution(self, service, mock_repository):
        """Test completing a pipeline execution."""
        execution_id = uuid4()
        artifacts = {"resume": "doc_123"}
        metrics = {"score": 0.95}

        mock_repository.get_execution = AsyncMock(
            return_value=CareerCopilotRun(
                id=str(execution_id),
                user_id=str(uuid4()),
                vacancy_id=str(uuid4()),
                profile_id=None,
                status=PipelineStatus.RUNNING,
            )
        )

        mock_repository.update_execution = AsyncMock()
        mock_repository.create_event = AsyncMock()

        await service.complete_execution(
            execution_id=execution_id,
            artifacts=artifacts,
            metrics=metrics,
        )

        mock_repository.update_execution.assert_called_once()
        mock_repository.create_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail_execution(self, service, mock_repository):
        """Test failing a pipeline execution."""
        execution_id = uuid4()

        mock_repository.get_execution = AsyncMock(
            return_value=CareerCopilotRun(
                id=str(execution_id),
                user_id=str(uuid4()),
                vacancy_id=str(uuid4()),
                profile_id=None,
                status=PipelineStatus.RUNNING,
            )
        )

        mock_repository.update_execution = AsyncMock()
        mock_repository.create_event = AsyncMock()

        await service.fail_execution(
            execution_id=execution_id,
            error_code="TEST_ERROR",
            error_message="Test error message",
            failed_step="mutation",
            retry_count=3,
            failure_category="transient",
            retryable=True,
        )

        mock_repository.update_execution.assert_called_once()
        call_args = mock_repository.update_execution.call_args
        assert call_args[1]["error_code"] == "TEST_ERROR"
        assert call_args[1]["error_message"] == "Test error message"
        assert call_args[1]["failed_step"] == "mutation"
        assert call_args[1]["retry_count"] == 3
        assert call_args[1]["metrics"]["failure"] == {
            "category": "transient",
            "retryable": True,
            "retry_count": 3,
            "failed_step": "mutation",
        }
        event_args = mock_repository.create_event.call_args[1]
        assert event_args["event_type"] == "execution_failed"
        assert event_args["payload"]["error_type"] == "TEST_ERROR"
        assert event_args["payload"]["message"] == "Test error message"
        assert event_args["payload"]["failed_step"] == "mutation"
        assert event_args["payload"]["retry_count"] == 3
        assert event_args["payload"]["failure_category"] == "transient"
        assert event_args["payload"]["retryable"] is True

    @pytest.mark.asyncio
    async def test_cancel_execution(self, service, mock_repository):
        execution_id = uuid4()
        execution = CareerCopilotRun(
            id=str(execution_id),
            user_id=str(uuid4()),
            vacancy_id=str(uuid4()),
            profile_id=None,
            status=PipelineStatus.RUNNING,
            metrics={"existing": True},
        )
        mock_repository.get_execution = AsyncMock(return_value=execution)
        mock_repository.update_execution = AsyncMock()
        mock_repository.create_event = AsyncMock()

        await service.cancel_execution(
            execution_id=execution_id,
            reason="manual stop",
        )

        mock_repository.update_execution.assert_called_once()
        call_args = mock_repository.update_execution.call_args[1]
        assert call_args["status"] == PipelineStatus.CANCELLED
        assert call_args["error_message"] == "manual stop"
        assert call_args["metrics"] == {
            "existing": True,
            "cancellation": {
                "reason": "manual stop",
                "cancelled_from_status": "running",
            },
        }
        event_args = mock_repository.create_event.call_args[1]
        assert event_args["event_type"] == "execution_cancelled"
        assert event_args["payload"]["reason"] == "manual stop"

    @pytest.mark.asyncio
    async def test_cancel_execution_rejects_completed_execution(self, service, mock_repository):
        execution_id = uuid4()
        mock_repository.get_execution = AsyncMock(
            return_value=CareerCopilotRun(
                id=str(execution_id),
                user_id=str(uuid4()),
                vacancy_id=str(uuid4()),
                profile_id=None,
                status=PipelineStatus.COMPLETED,
            )
        )
        mock_repository.update_execution = AsyncMock()

        with pytest.raises(ValueError, match="Execution cannot be cancelled"):
            await service.cancel_execution(execution_id=execution_id)

        mock_repository.update_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_cancelled(self, service, mock_repository):
        execution_id = uuid4()
        mock_repository.get_execution = AsyncMock(
            return_value=CareerCopilotRun(
                id=str(execution_id),
                user_id=str(uuid4()),
                vacancy_id=str(uuid4()),
                profile_id=None,
                status=PipelineStatus.CANCELLED,
            )
        )

        assert await service.is_cancelled(execution_id) is True

        mock_repository.get_execution = AsyncMock(
            return_value=CareerCopilotRun(
                id=str(execution_id),
                user_id=str(uuid4()),
                vacancy_id=str(uuid4()),
                profile_id=None,
                status=PipelineStatus.RUNNING,
            )
        )

        assert await service.is_cancelled(execution_id) is False

    def test_transition_status_rejects_invalid_transitions(self, service):
        with pytest.raises(ValueError):
            service._transition_status(
                PipelineExecutionStatus.COMPLETED,
                PipelineExecutionStatus.RUNNING,
            )

        with pytest.raises(ValueError):
            service._transition_status(
                PipelineExecutionStatus.FAILED,
                PipelineExecutionStatus.RUNNING,
            )

    def test_transition_status_allows_valid_transitions(self, service):
        assert service._transition_status(
            PipelineExecutionStatus.CREATED,
            PipelineExecutionStatus.RUNNING,
        ) == PipelineExecutionStatus.RUNNING
        assert service._transition_status(
            PipelineExecutionStatus.RUNNING,
            PipelineExecutionStatus.REVIEW_REQUIRED,
        ) == PipelineExecutionStatus.REVIEW_REQUIRED

    @pytest.mark.asyncio
    async def test_start_step(self, service, mock_repository):
        """Test starting a pipeline step."""
        execution_id = uuid4()

        mock_step = PipelineExecutionStep(
            id=str(uuid4()),
            execution_id=str(execution_id),
            step_name="test_step",
            status=StepStatus.PENDING,
        )

        mock_repository.create_step = AsyncMock(return_value=mock_step)
        mock_repository.update_step = AsyncMock()
        mock_repository.create_event = AsyncMock()

        step = await service.start_step(
            execution_id=execution_id,
            step_name="test_step",
            input_artifact_ids=["input_1"],
        )

        assert step.step_name == "test_step"
        mock_repository.create_step.assert_called_once()

    def test_serialize_execution_event_payload(self):
        payload = ExecutionStartedPayload(
            pipeline_version="v1.0",
            calibration_version="calib-v2",
        )

        serialized = serialize_execution_event_payload(payload)

        assert serialized == {
            "pipeline_version": "v1.0",
            "calibration_version": "calib-v2",
        }

    def test_serialize_execution_event_payload_converts_uuid(self):
        from uuid import uuid4
        from app.domain.execution_event_payloads import RecommendationAppliedPayload

        payload = RecommendationAppliedPayload(
            recommendation_id="rec-1",
            task_type="add_evidence",
            document_id=uuid4(),
        )

        serialized = serialize_execution_event_payload(payload)

        assert serialized["recommendation_id"] == "rec-1"
        assert serialized["task_type"] == "add_evidence"
        assert isinstance(serialized["document_id"], str)

    @pytest.mark.asyncio
    async def test_stuck_execution_service_marks_old_running_executions_failed(self):
        execution_id = uuid4()
        old_started_at = datetime.now(timezone.utc) - timedelta(hours=1)

        stuck_execution = CareerCopilotRun(
            id=str(execution_id),
            user_id=str(uuid4()),
            vacancy_id=str(uuid4()),
            profile_id=None,
            status=PipelineStatus.RUNNING,
            started_at=old_started_at,
            retry_count=2,
        )

        mock_repository = MagicMock(spec=SQLAlchemyAsyncPipelineRepository)
        mock_repository.get_stuck_executions = AsyncMock(return_value=[stuck_execution])
        mock_repository.get_execution = AsyncMock(return_value=stuck_execution)
        mock_repository.update_execution = AsyncMock()
        mock_repository.create_event = AsyncMock()

        pipeline_service = PipelineExecutionService(repository=mock_repository)
        stuck_service = StuckExecutionService(
            pipeline_service=pipeline_service,
            threshold_minutes=30,
        )

        marked = await stuck_service.mark_stuck_executions_failed()

        assert marked == 1

        mock_repository.update_execution.assert_called_once()
        call_args = mock_repository.update_execution.call_args[1]
        assert call_args["status"] == PipelineStatus.FAILED
        assert call_args["failed_step"] == "stuck_execution_detector"
        assert call_args["error_code"] == "StuckExecutionTimeout"
        assert call_args["retry_count"] == 2
        assert call_args["metrics"]["failure"]["category"] == "transient"
        assert call_args["metrics"]["failure"]["retryable"] is True

    @pytest.mark.asyncio
    async def test_orchestrator_returns_cancelled_execution_without_fail_execution(
        self,
        db_session,
        monkeypatch,
    ):
        user_id = uuid4()
        document_id = uuid4()
        vacancy_id = uuid4()
        execution_id = uuid4()
        fail_calls: list[dict] = []

        async def start_execution_spy(self, **kwargs):
            return CareerCopilotRun(
                id=str(execution_id),
                user_id=str(user_id),
                document_id=str(document_id),
                vacancy_id=str(vacancy_id),
                profile_id=None,
                status=PipelineStatus.RUNNING,
            )

        async def always_cancelled(self, execution_id):
            return True

        async def fail_execution_spy(self, **kwargs):
            fail_calls.append(kwargs)

        async def get_cancelled_execution(self, execution_id):
            return CareerCopilotRun(
                id=str(execution_id),
                user_id=str(user_id),
                document_id=str(document_id),
                vacancy_id=str(vacancy_id),
                profile_id=None,
                status=PipelineStatus.CANCELLED,
            )

        monkeypatch.setattr(PipelineExecutionService, "start_execution", start_execution_spy)
        monkeypatch.setattr(PipelineExecutionService, "is_cancelled", always_cancelled)
        monkeypatch.setattr(PipelineExecutionService, "fail_execution", fail_execution_spy)
        monkeypatch.setattr(SQLAlchemyAsyncPipelineRepository, "get_execution", get_cancelled_execution)

        orchestrator = CareerPipelineOrchestrator()
        result = await orchestrator.run_pipeline(
            session=db_session,
            document_id=document_id,
            vacancy_id=vacancy_id,
            user_id=user_id,
        )

        assert result.status == PipelineStatus.CANCELLED
        assert fail_calls == []

    @pytest.mark.asyncio
    async def test_execution_observability_service_returns_runtime_snapshot(self):
        aggregate = ExecutionRuntimeAggregate(
            running_count=2,
            completed_count=5,
            failed_count=1,
            cancelled_count=1,
            retry_total=3,
            avg_execution_duration_ms=1200.0,
            avg_evaluation_duration_ms=400.0,
            avg_mutation_duration_ms=300.0,
        )
        pipeline_repository = MagicMock()
        pipeline_repository.get_runtime_aggregate = AsyncMock(return_value=aggregate)
        stuck_pipeline_service = SimpleNamespace(
            get_stuck_executions=AsyncMock(return_value=[object(), object()])
        )
        stuck_service = SimpleNamespace(_pipeline_service=stuck_pipeline_service)
        observability_service = ExecutionObservabilityService(
            pipeline_repository=pipeline_repository,
            stuck_execution_service=stuck_service,
        )

        snapshot = await observability_service.get_execution_runtime_snapshot(MagicMock())

        assert snapshot.running_count == 2
        assert snapshot.completed_count == 5
        assert snapshot.failed_count == 1
        assert snapshot.cancelled_count == 1
        assert snapshot.retry_total == 3
        assert snapshot.stuck_count == 2
        assert snapshot.avg_execution_duration_ms == 1200.0
        assert snapshot.avg_evaluation_duration_ms == 400.0
        assert snapshot.avg_mutation_duration_ms == 300.0
