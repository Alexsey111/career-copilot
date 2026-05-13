# tests/evals/test_retry_policy.py

"""Tests for retry policy and pipeline recovery."""

from __future__ import annotations

import pytest
from datetime import datetime
from uuid import uuid4

from app.services.retry_policy import (
    RetryPolicy,
    BackoffStrategy,
    RecoveryPoint,
    ExecutionRecoveryState,
    PipelineRecoveryManager,
    resume_execution_from_step,
)


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_default_policy(self):
        """Test default retry policy values."""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.retryable_steps == []
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.base_delay_sec == 1.0
        assert policy.max_delay_sec == 60.0

    def test_is_retryable_with_empty_list(self):
        """When retryable_steps is empty, all steps are retryable."""
        policy = RetryPolicy(retryable_steps=[])

        assert policy.is_retryable("any_step")
        assert policy.is_retryable("document_evaluation")

    def test_is_retryable_with_specific_steps(self):
        """When retryable_steps has values, only those are retryable."""
        policy = RetryPolicy(retryable_steps=["document_evaluation", "readiness_scoring"])

        assert policy.is_retryable("document_evaluation")
        assert policy.is_retryable("readiness_scoring")
        assert not policy.is_retryable("profile_loading")

    def test_calculate_delay_fixed(self):
        """Test fixed backoff strategy."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.FIXED,
            base_delay_sec=2.0,
        )

        assert policy.calculate_delay(0) == 0.0
        assert policy.calculate_delay(1) == 2.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(10) == 2.0

    def test_calculate_delay_linear(self):
        """Test linear backoff strategy."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay_sec=1.0,
        )

        assert policy.calculate_delay(0) == 0.0
        assert policy.calculate_delay(1) == 1.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(5) == 5.0

    def test_calculate_delay_exponential(self):
        """Test exponential backoff strategy."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_sec=1.0,
        )

        assert policy.calculate_delay(0) == 0.0
        assert policy.calculate_delay(1) == 1.0  # 1 * 2^0
        assert policy.calculate_delay(2) == 2.0  # 1 * 2^1
        assert policy.calculate_delay(3) == 4.0  # 1 * 2^2
        assert policy.calculate_delay(4) == 8.0  # 1 * 2^3

    def test_calculate_delay_respects_max(self):
        """Test that delay respects max_delay_sec."""
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_sec=10.0,
            max_delay_sec=30.0,
        )

        # 10 * 2^4 = 160, but should be capped at 30
        assert policy.calculate_delay(5) == 30.0

    def test_should_retry_respects_max_retries(self):
        """Test that retry stops after max_retries."""
        policy = RetryPolicy(max_retries=3)

        assert policy.should_retry("step", 0)
        assert policy.should_retry("step", 1)
        assert policy.should_retry("step", 2)
        assert not policy.should_retry("step", 3)
        assert not policy.should_retry("step", 4)

    def test_should_retry_respects_retryable_steps(self):
        """Test that only retryable steps are retried."""
        policy = RetryPolicy(
            max_retries=3,
            retryable_steps=["retryable_step"],
        )

        assert policy.should_retry("retryable_step", 0)
        assert not policy.should_retry("non_retryable_step", 0)


class TestPipelineRecoveryManager:
    """Tests for PipelineRecoveryManager."""

    @pytest.fixture
    def manager(self):
        return PipelineRecoveryManager()

    def test_record_step_success(self, manager):
        """Test recording successful step completion."""
        execution_id = str(uuid4())
        step_id = str(uuid4())

        manager.record_step_success(
            execution_id=execution_id,
            step_id=step_id,
            step_name="document_evaluation",
            output_artifact_ids=["artifact-1"],
            metadata={"duration_ms": 1000},
        )

        state = manager.get_recovery_state(execution_id)
        assert state is not None
        assert state.last_successful_step is not None
        assert state.last_successful_step.step_name == "document_evaluation"
        assert state.last_successful_step.step_id == step_id
        assert state.last_successful_step.output_artifact_ids == ["artifact-1"]

    def test_record_step_failure(self, manager):
        """Test recording step failure."""
        execution_id = str(uuid4())

        manager.record_step_failure(
            execution_id=execution_id,
            step_name="readiness_scoring",
            error_message="Score calculation failed",
        )

        state = manager.get_recovery_state(execution_id)
        assert state is not None
        assert state.failed_step == "readiness_scoring"
        assert state.error_message == "Score calculation failed"
        assert state.failed_at is not None

    def test_multiple_steps_success(self, manager):
        """Test recording multiple successful steps."""
        execution_id = str(uuid4())

        manager.record_step_success(
            execution_id=execution_id,
            step_id="step-1",
            step_name="profile_loading",
            output_artifact_ids=["artifact-1"],
        )

        manager.record_step_success(
            execution_id=execution_id,
            step_id="step-2",
            step_name="vacancy_analysis",
            output_artifact_ids=["artifact-2"],
        )

        state = manager.get_recovery_state(execution_id)
        assert state.last_successful_step.step_name == "vacancy_analysis"

    def test_mark_recovered(self, manager):
        """Test marking execution as recovered."""
        execution_id = str(uuid4())

        manager.record_step_success(
            execution_id=execution_id,
            step_id="step-1",
            step_name="profile_loading",
            output_artifact_ids=[],
        )

        manager.mark_recovered(execution_id)

        state = manager.get_recovery_state(execution_id)
        assert state.recovered is True
        assert state.recovered_at is not None

    def test_get_resumable_step(self, manager):
        """Test determining resumable step."""
        execution_id = str(uuid4())

        manager.record_step_success(
            execution_id=execution_id,
            step_id="step-1",
            step_name="profile_loading",
            output_artifact_ids=[],
        )

        next_step = manager.get_resumable_step(execution_id)
        assert next_step == "vacancy_analysis"

    def test_get_resumable_step_unknown(self, manager):
        """Test resumable step for unknown step name."""
        execution_id = str(uuid4())

        manager.record_step_success(
            execution_id=execution_id,
            step_id="step-1",
            step_name="unknown_step",
            output_artifact_ids=[],
        )

        next_step = manager.get_resumable_step(execution_id)
        assert next_step is None

    def test_get_resumable_step_no_state(self, manager):
        """Test resumable step when no state exists."""
        execution_id = str(uuid4())
        next_step = manager.get_resumable_step(execution_id)
        assert next_step is None


class TestResumeExecutionFromStep:
    """Tests for resume_execution_from_step function."""

    def test_resume_basic(self):
        """Test basic resume functionality."""
        execution_id = uuid4()

        result = resume_execution_from_step(
            execution_id=execution_id,
            target_step="readiness_scoring",
        )

        assert result["success"] is True
        assert result["execution_id"] == str(execution_id)
        assert result["resumed_step"] == "readiness_scoring"

    def test_resume_with_input_artifacts(self):
        """Test resume with input artifacts."""
        execution_id = uuid4()
        input_artifacts = {"resume": {"content": "test"}}

        result = resume_execution_from_step(
            execution_id=execution_id,
            target_step="document_evaluation",
            input_artifacts=input_artifacts,
        )

        assert result["input_artifacts"] == input_artifacts

    def test_resume_with_override_parameters(self):
        """Test resume with parameter overrides."""
        execution_id = uuid4()
        overrides = {"calibration_version": "v2.0"}

        result = resume_execution_from_step(
            execution_id=execution_id,
            target_step="coverage_mapping",
            override_parameters=overrides,
        )

        assert result["override_parameters"] == overrides
