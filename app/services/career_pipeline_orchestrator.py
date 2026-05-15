"""CareerPipelineOrchestrator — single orchestration entrypoint for the career pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pipeline_models import CareerCopilotRun as PipelineExecution
from app.domain.readiness_models import RecommendationCategory, RecommendationItem, ReadinessScore
from app.domain.recommendation_models import RecommendationPriority, RecommendationTask, RecommendationTaskType
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.impact_measurement_repository import ImpactMeasurementRepository
from app.repositories.pipeline_execution_event_repository import PipelineExecutionEventRepository
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.repositories.review_workflow_repository import ReviewWorkflowRepository
from app.services.deterministic_scoring_service import DeterministicScoringService
from app.services.document_mutation_service import DocumentMutationService
from app.services.document_review_service import DocumentReviewService
from app.services.impact_measurement_service import ImpactMeasurementService
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.readiness_evaluation_service import ReadinessEvaluationService
from app.services.readiness_feature_extraction_service import ReadinessFeatureExtractionService
from app.services.recommendation_task_service import RecommendationTaskService

logger = logging.getLogger(__name__)


class CareerPipelineOrchestrator:
    """Owns the full pipeline flow and keeps routes thin."""

    def __init__(self, ai_service: Any | None = None) -> None:
        self._ai_service = ai_service or object()

    async def run_pipeline(
        self,
        session: AsyncSession,
        document_id: UUID,
        vacancy_id: UUID,
        user_id: UUID,
    ) -> PipelineExecution:
        document_repo = DocumentVersionRepository()
        pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=session)
        event_repo = PipelineExecutionEventRepository()
        review_repo = ReviewWorkflowRepository()
        impact_repo = ImpactMeasurementRepository()

        pipeline_service = PipelineExecutionService(
            repository=pipeline_repo,
            event_repository=event_repo,
        )
        evaluation_service = ReadinessEvaluationService(
            feature_extraction_service=ReadinessFeatureExtractionService(self._ai_service),
            scoring_service=DeterministicScoringService(),
            document_repository=document_repo,
        )
        recommendation_service = RecommendationTaskService()
        mutation_service = DocumentMutationService(document_repo)
        impact_service = ImpactMeasurementService(impact_repo)
        review_service = DocumentReviewService(
            document_version_repository=document_repo,
            review_workflow_repository=review_repo,
        )

        execution = await pipeline_service.start_execution(
            user_id=user_id,
            vacancy_id=vacancy_id,
            profile_id=None,
            pipeline_version="v1.0",
            session=session,
        )

        before_started_at = datetime.now(timezone.utc)
        before_evaluation, before_snapshot_id = await evaluation_service.evaluate_document(
            session,
            document_id=document_id,
            user_id=user_id,
        )
        before_completed_at = datetime.now(timezone.utc)
        before_score = self._evaluation_to_score(before_evaluation)
        before_tasks = recommendation_service.prioritize_tasks(
            recommendation_service.generate_tasks_from_readiness(before_score)
        )
        await pipeline_service.record_evaluation_completed(
            execution_id=UUID(execution.id),
            evaluation_summary={
                "phase": "initial",
                "snapshot_id": str(before_snapshot_id),
                "overall_score": before_evaluation.overall_score,
                "duration_ms": int((before_completed_at - before_started_at).total_seconds() * 1000),
                "ats_score": before_evaluation.ats_score,
                "coverage_score": before_evaluation.coverage_score,
                "evidence_score": before_evaluation.evidence_score,
                "quality_score": before_evaluation.quality_score,
                "blocking_issues": before_evaluation.blockers,
                "warnings": before_evaluation.warnings,
            },
            session=session,
        )

        primary_task = before_tasks[0] if before_tasks else self._build_fallback_task(before_score)
        changes = self._build_changes_from_task(primary_task, before_evaluation)
        recommendation_id = self._build_recommendation_id(primary_task)

        mutation_started_at = datetime.now(timezone.utc)
        mutated_document = await mutation_service.apply_recommendation(
            session=session,
            document_id=document_id,
            recommendation_id=recommendation_id,
            changes=changes,
            user_id=user_id,
        )
        mutation_completed_at = datetime.now(timezone.utc)

        after_evaluation, after_snapshot_id = await evaluation_service.evaluate_document(
            session,
            document_id=mutated_document.id,
            user_id=user_id,
        )
        after_completed_at = datetime.now(timezone.utc)
        after_score = self._evaluation_to_score(after_evaluation)
        after_tasks = recommendation_service.prioritize_tasks(
            recommendation_service.generate_tasks_from_readiness(after_score)
        )
        await pipeline_service.record_evaluation_completed(
            execution_id=UUID(execution.id),
            evaluation_summary={
                "phase": "post_mutation",
                "snapshot_id": str(after_snapshot_id),
                "overall_score": after_evaluation.overall_score,
                "duration_ms": int((after_completed_at - mutation_completed_at).total_seconds() * 1000),
                "ats_score": after_evaluation.ats_score,
                "coverage_score": after_evaluation.coverage_score,
                "evidence_score": after_evaluation.evidence_score,
                "quality_score": after_evaluation.quality_score,
                "blocking_issues": after_evaluation.blockers,
                "warnings": after_evaluation.warnings,
            },
            session=session,
        )

        await pipeline_service.record_recommendation_applied(
            execution_id=UUID(execution.id),
            recommendation_data={
                "recommendation_id": recommendation_id,
                "task_type": primary_task.task_type.value,
                "document_id": str(mutated_document.id),
            },
            session=session,
        )

        impact_started_at = mutation_started_at
        impact_completed_at = after_completed_at
        impact_measurement = await impact_service.measure_impact(
            session=session,
            recommendation_id=recommendation_id,
            recommendation_type=primary_task.task_type.value,
            target_achievement_id=primary_task.target_achievement_id,
            changes=changes,
            before_evaluation=before_evaluation,
            after_evaluation=after_evaluation,
            before_snapshot_id=before_snapshot_id,
            after_snapshot_id=after_snapshot_id,
            document_id=mutated_document.id,
            started_at=impact_started_at,
            completed_at=impact_completed_at,
        )

        review_required, review_reason = self._needs_review(after_evaluation, after_tasks)
        review_session = None
        if review_required:
            review_session = await review_service.start_review(
                session,
                document_id=mutated_document.id,
                user_id=user_id,
                review_required=True,
                review_reason=review_reason,
                pipeline_execution_id=UUID(execution.id),
                metadata={
                    "primary_task": self._task_payload(primary_task),
                    "readiness_before": self._evaluation_payload(before_evaluation),
                    "readiness_after": self._evaluation_payload(after_evaluation),
                },
            )
            await pipeline_service.record_review_required(
                execution_id=UUID(execution.id),
                review_reason=review_reason,
                session=session,
            )

        artifacts = {
            "document_id": str(document_id),
            "mutated_document_id": str(mutated_document.id),
            "before_snapshot_id": str(before_snapshot_id),
            "after_snapshot_id": str(after_snapshot_id),
            "recommendation_id": recommendation_id,
            "primary_task": self._task_payload(primary_task),
            "review_session_id": str(review_session.id) if review_session is not None else None,
        }
        metrics = {
            "readiness_score": self._evaluation_payload(after_evaluation),
            "review_required": review_required,
            "impact": {
                "readiness_delta": impact_measurement.readiness_delta.delta,
                "time_to_complete_seconds": impact_measurement.time_to_complete_seconds,
            },
        }

        await pipeline_service.complete_execution(
            execution_id=UUID(execution.id),
            artifacts=artifacts,
            metrics=metrics,
            resume_document_id=mutated_document.id,
            review_required=review_required,
            review_completed=False,
            evaluation_duration_ms=int((before_completed_at - before_started_at).total_seconds() * 1000),
            mutation_duration_ms=int((mutation_completed_at - mutation_started_at).total_seconds() * 1000),
            session=session,
        )

        logger.info(
            "Career pipeline completed",
            extra={
                "execution_id": str(execution.id),
                "document_id": str(mutated_document.id),
                "review_required": review_required,
            },
        )

        return await pipeline_repo.get_execution(UUID(execution.id)) or execution

    def _evaluation_to_score(self, evaluation) -> ReadinessScore:
        return ReadinessScore(
            overall_score=evaluation.overall_score,
            ats_score=evaluation.ats_score,
            evidence_score=evaluation.evidence_score,
            coverage_score=evaluation.coverage_score,
            quality_score=evaluation.quality_score,
            interview_score=0.0,
            blocking_issues=list(evaluation.blockers or []),
            warnings=list(evaluation.warnings or []),
            recommendations=[
                RecommendationItem(message=message, category=RecommendationCategory.GENERAL, severity="error")
                for message in evaluation.blockers or []
            ]
            + [
                RecommendationItem(message=message, category=RecommendationCategory.GENERAL, severity="warning")
                for message in evaluation.warnings or []
            ],
        )

    def _build_fallback_task(self, readiness_score: ReadinessScore) -> RecommendationTask:
        return RecommendationTask(
            task_type=RecommendationTaskType.ADD_EVIDENCE,
            priority=RecommendationPriority.MEDIUM,
            blocking=False,
            description="Improve the document with one targeted evidence update",
            rationale="Fallback task generated because no explicit recommendation tasks were produced",
            estimated_score_improvement=0.0,
            confidence=0.1,
            metadata={
                "source": "career_pipeline_orchestrator",
                "overall_score": readiness_score.overall_score,
            },
        )

    def _build_recommendation_id(self, task: RecommendationTask) -> str:
        return f"{task.task_type.value}-{task.priority.value}"

    def _build_changes_from_task(
        self,
        task: RecommendationTask,
        evaluation,
    ) -> dict[str, Any]:
        return {
            "operations": [
                {
                    "section": "meta",
                    "operation": "merge",
                    "extra": {
                        "pipeline_task_type": task.task_type.value,
                        "pipeline_task_description": task.description,
                        "pipeline_task_rationale": task.rationale,
                        "pipeline_primary_warning_count": len(evaluation.warnings or []),
                    },
                }
            ]
        }

    def _needs_review(
        self,
        evaluation,
        tasks: list[RecommendationTask],
    ) -> tuple[bool, str]:
        if evaluation.blockers:
            return True, evaluation.blockers[0]

        if any(task.blocking for task in tasks):
            blocking_task = next(task for task in tasks if task.blocking)
            return True, blocking_task.rationale or blocking_task.description

        if evaluation.overall_score < 0.7:
            return True, "Readiness score below review threshold"

        return False, "No manual review required"

    def _evaluation_payload(self, evaluation) -> dict[str, Any]:
        return {
            "overall_score": evaluation.overall_score,
            "ats_score": evaluation.ats_score,
            "evidence_score": evaluation.evidence_score,
            "coverage_score": evaluation.coverage_score,
            "quality_score": evaluation.quality_score,
            "blockers": list(evaluation.blockers or []),
            "warnings": list(evaluation.warnings or []),
        }

    def _task_payload(self, task: RecommendationTask) -> dict[str, Any]:
        return {
            "task_type": task.task_type.value,
            "priority": task.priority.value,
            "blocking": task.blocking,
            "description": task.description,
            "rationale": task.rationale,
            "target_achievement_id": task.target_achievement_id,
            "confidence": task.confidence,
        }
