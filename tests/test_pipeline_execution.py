from __future__ import annotations

import pytest
from datetime import datetime
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
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.services.pipeline_execution_service import PipelineExecutionService


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
    async def test_complete_execution(self, service, mock_repository):
        """Test completing a pipeline execution."""
        execution_id = uuid4()
        artifacts = {"resume": "doc_123"}
        metrics = {"score": 0.95}

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

        mock_repository.update_execution = AsyncMock()
        mock_repository.create_event = AsyncMock()

        await service.fail_execution(
            execution_id=execution_id,
            error_code="TEST_ERROR",
            error_message="Test error message",
        )

        mock_repository.update_execution.assert_called_once()
        call_args = mock_repository.update_execution.call_args
        assert call_args[1]["error_code"] == "TEST_ERROR"
        assert call_args[1]["error_message"] == "Test error message"
        event_args = mock_repository.create_event.call_args[1]
        assert event_args["event_type"] == "execution_failed"
        assert event_args["payload"]["error_type"] == "TEST_ERROR"
        assert event_args["payload"]["message"] == "Test error message"

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
