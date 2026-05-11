from datetime import datetime

from app.domain.pipeline_models import CareerCopilotRun, PipelineStatus
from app.repositories.pipeline_repository import InMemoryPipelineRepository


class TestInMemoryPipelineRepository:

    def test_save_and_get_run(self) -> None:
        """Test saving and retrieving a pipeline run."""
        repo = InMemoryPipelineRepository()

        run = CareerCopilotRun(
            id="test_run_123",
            user_id="user_456",
            vacancy_id="vacancy_789",
            profile_id="profile_101",
            status=PipelineStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )

        repo.save_run(run)

        retrieved = repo.get_run("test_run_123")
        assert retrieved is not None
        assert retrieved.id == "test_run_123"
        assert retrieved.user_id == "user_456"
        assert retrieved.status == PipelineStatus.COMPLETED

    def test_get_nonexistent_run(self) -> None:
        """Test getting a run that doesn't exist."""
        repo = InMemoryPipelineRepository()

        retrieved = repo.get_run("nonexistent")
        assert retrieved is None

    def test_get_runs_for_user(self) -> None:
        """Test getting runs for a specific user."""
        repo = InMemoryPipelineRepository()

        # Create runs for different users
        run1 = CareerCopilotRun(
            id="run1",
            user_id="user1",
            vacancy_id="vac1",
            profile_id="prof1",
            started_at=datetime(2024, 1, 1),
        )
        run2 = CareerCopilotRun(
            id="run2",
            user_id="user1",
            vacancy_id="vac2",
            profile_id="prof2",
            started_at=datetime(2024, 1, 2),
        )
        run3 = CareerCopilotRun(
            id="run3",
            user_id="user2",
            vacancy_id="vac3",
            profile_id="prof3",
            started_at=datetime(2024, 1, 3),
        )

        repo.save_run(run1)
        repo.save_run(run2)
        repo.save_run(run3)

        user_runs = repo.get_runs_for_user("user1", limit=10)
        assert len(user_runs) == 2
        # Should be sorted by started_at descending
        assert user_runs[0].id == "run2"
        assert user_runs[1].id == "run1"

    def test_get_runs_for_vacancy(self) -> None:
        """Test getting runs for a specific vacancy."""
        repo = InMemoryPipelineRepository()

        run1 = CareerCopilotRun(
            id="run1",
            user_id="user1",
            vacancy_id="vac1",
            profile_id="prof1",
        )
        run2 = CareerCopilotRun(
            id="run2",
            user_id="user2",
            vacancy_id="vac1",
            profile_id="prof2",
        )

        repo.save_run(run1)
        repo.save_run(run2)

        vacancy_runs = repo.get_runs_for_vacancy("vac1")
        assert len(vacancy_runs) == 2