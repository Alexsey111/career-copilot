from datetime import datetime

from app.domain.pipeline_models import CareerCopilotRun, PipelineStatus


class TestCareerCopilotRun:

    def test_creation(self) -> None:
        """Test creating a CareerCopilotRun."""
        run = CareerCopilotRun(
            id="test_run_123",
            user_id="user_456",
            vacancy_id="vacancy_789",
            profile_id="profile_101",
        )

        assert run.id == "test_run_123"
        assert run.user_id == "user_456"
        assert run.vacancy_id == "vacancy_789"
        assert run.profile_id == "profile_101"
        assert run.status == PipelineStatus.PENDING
        assert run.resume_document_id is None
        assert run.evaluation_snapshot_id is None
        assert run.review_id is None
        assert run.started_at is None
        assert run.completed_at is None
        assert run.pipeline_version == "v1.0"
        assert run.error_message is None
        assert isinstance(run.created_at, datetime)
        assert isinstance(run.updated_at, datetime)

    def test_with_artifacts(self) -> None:
        """Test run with completed artifacts."""
        started_at = datetime.now()

        run = CareerCopilotRun(
            id="test_run_123",
            user_id="user_456",
            vacancy_id="vacancy_789",
            profile_id="profile_101",
            resume_document_id="doc_123",
            evaluation_snapshot_id="eval_456",
            review_id="review_789",
            status=PipelineStatus.COMPLETED,
            started_at=started_at,
            completed_at=datetime.now(),
            pipeline_version="v1.1",
        )

        assert run.resume_document_id == "doc_123"
        assert run.evaluation_snapshot_id == "eval_456"
        assert run.review_id == "review_789"
        assert run.status == PipelineStatus.COMPLETED
        assert run.started_at == started_at
        assert run.completed_at is not None
        assert run.pipeline_version == "v1.1"