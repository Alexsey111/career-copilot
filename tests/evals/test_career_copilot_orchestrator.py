from datetime import datetime

from app.services.career_copilot_orchestrator import DefaultCareerCopilotOrchestrator, ResumePipelineResult


class TestDefaultCareerCopilotOrchestrator:

    def test_run_resume_pipeline_success(self) -> None:
        """Test successful pipeline execution."""
        orchestrator = DefaultCareerCopilotOrchestrator()

        result = orchestrator.run_resume_pipeline(
            user_id="user_123",
            vacancy_id="vacancy_456",
            profile_id="profile_789",
        )

        assert isinstance(result, ResumePipelineResult)
        assert result.success is True
        assert result.run_id.startswith("run_user_123_vacancy_456_profile_789_")
        assert result.resume_document_id == "placeholder_resume_id"
        assert result.evaluation_snapshot_id == "placeholder_eval_id"
        assert result.review_id == "placeholder_review_id"
        assert result.readiness_score == 0.85
        assert result.review_required is True
        assert isinstance(result.recommendation_tasks, list)
        assert len(result.recommendation_tasks) > 0  # Should have generated tasks
        assert isinstance(result.started_at, datetime)
        assert result.completed_at is not None
        assert result.error_message is None

    def test_run_resume_pipeline_structure(self) -> None:
        """Test that pipeline result has correct structure."""
        orchestrator = DefaultCareerCopilotOrchestrator()

        result = orchestrator.run_resume_pipeline(
            user_id="test_user",
            vacancy_id="test_vacancy",
            profile_id="test_profile",
        )

        # Check all expected fields are present
        required_fields = [
            'run_id', 'success', 'resume_document_id', 'evaluation_snapshot_id',
            'review_id', 'readiness_score', 'review_required', 'recommendation_tasks', 'started_at',
            'completed_at', 'error_message'
        ]

        for field in required_fields:
            assert hasattr(result, field), f"Missing field: {field}"