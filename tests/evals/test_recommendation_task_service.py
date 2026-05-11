from app.domain.readiness_models import ReadinessScore, RecommendationItem
from app.domain.recommendation_models import RecommendationPriority, RecommendationTask, RecommendationTaskType
from app.services.recommendation_task_service import RecommendationTaskService


class TestRecommendationTaskService:

    def test_generate_tasks_from_readiness(self) -> None:
        """Test generating tasks from readiness score."""
        service = RecommendationTaskService()

        readiness = ReadinessScore(
            overall_score=0.7,
            recommendations=[
                RecommendationItem(
                    message="Add quantifiable results to demonstrate impact",
                    category="evidence",
                    severity="warning"
                ),
                RecommendationItem(
                    message="Strengthen evidence for key achievements",
                    category="evidence",
                    severity="info"
                ),
            ],
            evidence_score=0.5,
            coverage_score=0.6,
            blocking_issues=["Missing key evidence"],
        )

        tasks = service.generate_tasks_from_readiness(readiness)

        assert len(tasks) > 0

        # Check that tasks are generated from recommendations
        recommendation_tasks = [t for t in tasks if "recommendation_analysis" in t.metadata.get("source", "")]
        assert len(recommendation_tasks) >= 2

        # Check that tasks are generated from component scores
        component_tasks = [t for t in tasks if t.metadata.get("component") == "evidence"]
        assert len(component_tasks) > 0

        # Check that blocking issue tasks are generated
        blocking_tasks = [t for t in tasks if t.metadata.get("source") == "blocking_issue"]
        assert len(blocking_tasks) > 0

    def test_generate_task_from_recommendation(self) -> None:
        """Test generating a single task from recommendation."""
        service = RecommendationTaskService()

        recommendation = RecommendationItem(
            message="Add quantifiable results to demonstrate impact",
            category="evidence",
            severity="warning"
        )

        task = service._generate_task_from_recommendation(recommendation, ["ach_123"])

        assert task is not None
        assert task.task_type == RecommendationTaskType.ADD_METRIC
        assert task.target_achievement_id == "ach_123"
        assert task.priority == RecommendationPriority.HIGH
        assert task.blocking is False
        assert "quantifiable results" in task.description

    def test_prioritize_tasks(self) -> None:
        """Test task prioritization."""
        service = RecommendationTaskService()

        tasks = [
            RecommendationTask(
                task_type=RecommendationTaskType.ADD_EVIDENCE,
                priority=RecommendationPriority.LOW,
                blocking=False,
            ),
            RecommendationTask(
                task_type=RecommendationTaskType.ADD_METRIC,
                priority=RecommendationPriority.HIGH,
                blocking=True,
            ),
            RecommendationTask(
                task_type=RecommendationTaskType.IMPROVE_DESCRIPTION,
                priority=RecommendationPriority.MEDIUM,
                blocking=False,
            ),
        ]

        prioritized = service.prioritize_tasks(tasks)

        # Blocking high priority should be first
        assert prioritized[0].blocking is True
        assert prioritized[0].priority == RecommendationPriority.HIGH

        # Then non-blocking by priority
        assert prioritized[1].priority == RecommendationPriority.MEDIUM
        assert prioritized[2].priority == RecommendationPriority.LOW