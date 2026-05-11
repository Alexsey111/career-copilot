from __future__ import annotations

from typing import Dict, List, Optional

from app.domain.readiness_models import ReadinessScore, RecommendationItem
from app.domain.recommendation_models import (
    RecommendationPriority,
    RecommendationTask,
    RecommendationTaskType,
)


class RecommendationTaskService:
    """Service for generating actionable recommendation tasks from readiness analysis."""

    def __init__(self) -> None:
        # Task generation patterns based on recommendation analysis
        self.task_patterns = {
            "weak_evidence": {
                "task_type": RecommendationTaskType.ADD_EVIDENCE,
                "priority": RecommendationPriority.HIGH,
                "blocking": True,
                "description": "Add specific evidence or examples to support this achievement",
                "expected_improvement": 0.15,
            },
            "missing_metrics": {
                "task_type": RecommendationTaskType.ADD_METRIC,
                "priority": RecommendationPriority.HIGH,
                "blocking": False,
                "description": "Add quantifiable results or metrics to demonstrate impact",
                "expected_improvement": 0.12,
            },
            "vague_description": {
                "task_type": RecommendationTaskType.IMPROVE_DESCRIPTION,
                "priority": RecommendationPriority.MEDIUM,
                "blocking": False,
                "description": "Make the achievement description more specific and detailed",
                "expected_improvement": 0.08,
            },
            "no_timeframe": {
                "task_type": RecommendationTaskType.ADD_TIMEFRAME,
                "priority": RecommendationPriority.LOW,
                "blocking": False,
                "description": "Add specific time periods or durations to achievements",
                "expected_improvement": 0.05,
            },
            "missing_context": {
                "task_type": RecommendationTaskType.ADD_CONTEXT,
                "priority": RecommendationPriority.MEDIUM,
                "blocking": False,
                "description": "Add context about the situation, challenges, or environment",
                "expected_improvement": 0.07,
            },
            "redundant_content": {
                "task_type": RecommendationTaskType.REMOVE_REDUNDANT,
                "priority": RecommendationPriority.LOW,
                "blocking": False,
                "description": "Remove duplicate or redundant information",
                "expected_improvement": 0.03,
            },
        }

    def generate_tasks_from_readiness(
        self,
        readiness_score: ReadinessScore,
        achievement_ids: Optional[List[str]] = None,
    ) -> List[RecommendationTask]:
        """Generate actionable tasks from readiness score analysis."""
        tasks = []

        # Generate tasks from recommendations
        for recommendation in readiness_score.recommendations:
            task = self._generate_task_from_recommendation(recommendation, achievement_ids)
            if task:
                tasks.append(task)

        # Generate tasks from component scores
        component_tasks = self._generate_tasks_from_component_scores(readiness_score)
        tasks.extend(component_tasks)

        # Generate tasks from blocking issues
        blocking_tasks = self._generate_tasks_from_blocking_issues(readiness_score)
        tasks.extend(blocking_tasks)

        return tasks

    def _generate_task_from_recommendation(
        self,
        recommendation: RecommendationItem,
        achievement_ids: Optional[List[str]] = None,
    ) -> Optional[RecommendationTask]:
        """Generate a task from a single recommendation."""
        # Map recommendation message patterns to task types
        message_lower = recommendation.message.lower()

        if "evidence" in message_lower and ("weak" in message_lower or "missing" in message_lower):
            pattern = self.task_patterns["weak_evidence"]
        elif "metric" in message_lower or "quantifiable" in message_lower or "result" in message_lower:
            pattern = self.task_patterns["missing_metrics"]
        elif "description" in message_lower and ("vague" in message_lower or "specific" in message_lower):
            pattern = self.task_patterns["vague_description"]
        elif "time" in message_lower or "period" in message_lower:
            pattern = self.task_patterns["no_timeframe"]
        elif "context" in message_lower or "situation" in message_lower:
            pattern = self.task_patterns["missing_context"]
        elif "redundant" in message_lower or "duplicate" in message_lower:
            pattern = self.task_patterns["redundant_content"]
        else:
            # Default to evidence improvement
            pattern = self.task_patterns["weak_evidence"]

        # Determine target achievement (use first available or None)
        target_id = achievement_ids[0] if achievement_ids else None

        return RecommendationTask(
            task_type=pattern["task_type"],
            target_achievement_id=target_id,
            priority=pattern["priority"],
            blocking=pattern["blocking"],
            description=pattern["description"],
            rationale=recommendation.message,
            expected_score_improvement=pattern["expected_improvement"],
            metadata={"source": "recommendation_analysis", "severity": recommendation.severity},
        )

    def _generate_tasks_from_component_scores(self, readiness_score: ReadinessScore) -> List[RecommendationTask]:
        """Generate tasks based on low component scores."""
        tasks = []

        # Evidence score tasks
        if readiness_score.evidence_score < 0.6:
            tasks.append(RecommendationTask(
                task_type=RecommendationTaskType.ADD_EVIDENCE,
                priority=RecommendationPriority.HIGH if readiness_score.evidence_score < 0.4 else RecommendationPriority.MEDIUM,
                blocking=readiness_score.evidence_score < 0.3,
                description="Strengthen evidence and examples throughout the resume",
                rationale=f"Evidence score is {readiness_score.evidence_score:.2f}, needs improvement",
                expected_score_improvement=min(0.2, 1.0 - readiness_score.evidence_score),
                metadata={"component": "evidence", "current_score": readiness_score.evidence_score},
            ))

        # Coverage score tasks
        if readiness_score.coverage_score < 0.7:
            tasks.append(RecommendationTask(
                task_type=RecommendationTaskType.ADD_SKILL_KEYWORD,
                priority=RecommendationPriority.MEDIUM,
                blocking=False,
                description="Add relevant keywords and skills that match job requirements",
                rationale=f"Coverage score is {readiness_score.coverage_score:.2f}, missing key terms",
                expected_score_improvement=min(0.15, 1.0 - readiness_score.coverage_score),
                metadata={"component": "coverage", "current_score": readiness_score.coverage_score},
            ))

        return tasks

    def _generate_tasks_from_blocking_issues(self, readiness_score: ReadinessScore) -> List[RecommendationTask]:
        """Generate critical tasks from blocking issues."""
        tasks = []

        for issue in readiness_score.blocking_issues:
            issue_lower = issue.lower()

            if "evidence" in issue_lower:
                task_type = RecommendationTaskType.ADD_EVIDENCE
                description = "Address critical evidence gaps that are blocking approval"
            elif "metric" in issue_lower or "quantifiable" in issue_lower:
                task_type = RecommendationTaskType.ADD_METRIC
                description = "Add required quantifiable results or metrics"
            elif "description" in issue_lower:
                task_type = RecommendationTaskType.IMPROVE_DESCRIPTION
                description = "Fix critical description issues"
            else:
                task_type = RecommendationTaskType.ADD_EVIDENCE
                description = "Address critical blocking issue"

            tasks.append(RecommendationTask(
                task_type=task_type,
                priority=RecommendationPriority.CRITICAL,
                blocking=True,
                description=description,
                rationale=f"Blocking issue: {issue}",
                expected_score_improvement=0.2,
                metadata={"source": "blocking_issue", "issue": issue},
            ))

        return tasks

    def prioritize_tasks(self, tasks: List[RecommendationTask]) -> List[RecommendationTask]:
        """Sort tasks by priority and blocking status."""
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }

        return sorted(
            tasks,
            key=lambda t: (0 if t.blocking else 1, priority_order[t.priority], -t.expected_score_improvement)
        )