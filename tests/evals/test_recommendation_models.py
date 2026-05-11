from app.domain.recommendation_models import (
    RecommendationPriority,
    RecommendationTask,
    RecommendationTaskType,
)


class TestRecommendationTask:

    def test_creation(self) -> None:
        """Test creating a recommendation task."""
        task = RecommendationTask(
            task_type=RecommendationTaskType.ADD_METRIC,
            target_achievement_id="ach_123",
            priority=RecommendationPriority.HIGH,
            blocking=True,
            description="Add quantifiable results",
            rationale="Evidence is weak",
            expected_score_improvement=0.15,
        )

        assert task.task_type == RecommendationTaskType.ADD_METRIC
        assert task.target_achievement_id == "ach_123"
        assert task.priority == RecommendationPriority.HIGH
        assert task.blocking is True
        assert task.description == "Add quantifiable results"
        assert task.rationale == "Evidence is weak"
        assert task.expected_score_improvement == 0.15
        assert task.metadata == {}
        assert task.related_recommendation_ids == []

    def test_defaults(self) -> None:
        """Test default values."""
        task = RecommendationTask(task_type=RecommendationTaskType.ADD_EVIDENCE)

        assert task.priority == RecommendationPriority.MEDIUM
        assert task.blocking is False
        assert task.description == ""
        assert task.expected_score_improvement == 0.0