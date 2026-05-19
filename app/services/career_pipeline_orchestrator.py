"""CareerPipelineOrchestrator — single orchestration entrypoint for the career pipeline."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pipeline_models import CareerCopilotRun as PipelineExecution
from app.domain.readiness_models import RecommendationCategory, RecommendationItem, ReadinessScore
from app.domain.recommendation_models import RecommendationPriority, RecommendationTask, RecommendationTaskType
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.impact_measurement_repository import ImpactMeasurementRepository
from app.repositories.pipeline_execution_event_repository import PipelineExecutionEventRepository
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.review_workflow_repository import ReviewWorkflowRepository
from app.services.deterministic_scoring_service import DeterministicScoringService
from app.services.document_mutation_service import DocumentMutationService
from app.services.document_review_service import DocumentReviewService
from app.services.impact_measurement_service import ImpactMeasurementService
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.readiness_evaluation_service import ReadinessEvaluationService
from app.services.readiness_feature_extraction_service import ReadinessFeatureExtractionService
from app.services.recommendation_task_service import RecommendationTaskService
from app.core.tracing import get_trace_context, set_trace_context
from app.domain.failure_models import classify_failure, is_retryable_failure
from app.domain.pipeline_errors import PipelineCancelledError

logger = logging.getLogger(__name__)

T = TypeVar("T")


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
        idempotency_key: str | None = None,
        execution_id: UUID | None = None,
    ) -> PipelineExecution:
        document_repo = DocumentVersionRepository()
        pipeline_repo = SQLAlchemyAsyncPipelineRepository(session=session)
        event_repo = PipelineExecutionEventRepository()
        recommendation_repo = RecommendationRepository()
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

        if idempotency_key:
            existing_execution = await pipeline_repo.get_execution_by_idempotency_key(
                user_id=user_id,
                document_id=document_id,
                vacancy_id=vacancy_id,
                idempotency_key=idempotency_key,
            )
            if existing_execution is not None:
                set_trace_context(trace_id=existing_execution.id)
                return existing_execution

        if execution_id is not None:
            existing_execution = await pipeline_repo.get_execution(execution_id)
            if existing_execution is not None:
                set_trace_context(trace_id=existing_execution.id)
                return existing_execution

        execution = await pipeline_service.start_execution(
            user_id=user_id,
            execution_id=execution_id,
            document_id=document_id,
            vacancy_id=vacancy_id,
            profile_id=None,
            pipeline_version="v1.0",
            idempotency_key=idempotency_key,
            session=session,
        )
        await session.commit()

        before_started_at = datetime.now(timezone.utc)
        current_step = "evaluation"
        mutated_document = None
        before_evaluation = None
        before_snapshot_id = None
        before_completed_at = None
        before_score = None
        before_tasks: list[RecommendationTask] = []
        primary_task = None
        recommendation_records = []
        primary_recommendation = None
        changes: dict[str, Any] | None = None
        after_evaluation = None
        after_snapshot_id = None
        after_completed_at = None
        impact_measurement = None
        review_session = None
        review_required = False
        review_reason = "No manual review required"
        mutation_started_at = None
        mutation_completed_at = None
        try:
            async with session.begin():
                current_step = "initial_evaluation"
                before_evaluation, before_snapshot_id = await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="initial_evaluation",
                    fn=lambda: evaluation_service.evaluate_document(
                        session,
                        document_id=document_id,
                        user_id=user_id,
                    ),
                    output_artifact_ids=lambda result: [str(result[1])],
                )
                before_completed_at = datetime.now(timezone.utc)
                before_score = self._evaluation_to_score(before_evaluation)

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

                current_step = "recommendation_generation"
                before_tasks, primary_task, recommendation_records = await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="recommendation_generation",
                    fn=lambda: self._generate_and_persist_recommendations(
                        recommendation_service=recommendation_service,
                        recommendation_repo=recommendation_repo,
                        session=session,
                        execution_id=UUID(execution.id),
                        document_id=document_id,
                        readiness_score=before_score,
                    ),
                    output_artifact_ids=lambda result: [str(record.id) for record in result[2]],
                )
                primary_recommendation = recommendation_records[0]
                changes = self._build_changes_from_task(primary_task, before_evaluation)

                current_step = "mutation"
                mutation_started_at, mutated_document, mutation_completed_at = await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="mutation",
                    fn=lambda: self._apply_mutation(
                        mutation_service=mutation_service,
                        session=session,
                        document_id=document_id,
                        recommendation_id=primary_recommendation.id,
                        changes=changes,
                        user_id=user_id,
                    ),
                    output_artifact_ids=lambda result: [str(result[1].id)],
                )

                current_step = "after_evaluation"
                after_evaluation, after_snapshot_id = await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="after_evaluation",
                    fn=lambda: evaluation_service.evaluate_document(
                        session,
                        document_id=mutated_document.id,
                        user_id=user_id,
                    ),
                    output_artifact_ids=lambda result: [str(result[1])],
                )
                after_completed_at = datetime.now(timezone.utc)
                after_score = self._evaluation_to_score(after_evaluation)
                after_tasks = recommendation_service.prioritize_tasks(
                    recommendation_service.generate_tasks_from_readiness(after_score)
                )

                current_step = "impact_measurement"
                impact_measurement = await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="impact_measurement",
                    fn=lambda: impact_service.measure_impact(
                        session=session,
                        recommendation_id=str(primary_recommendation.id),
                        recommendation_type=primary_task.task_type.value,
                        target_achievement_id=primary_task.target_achievement_id,
                        changes=changes,
                        before_evaluation=before_evaluation,
                        after_evaluation=after_evaluation,
                        before_snapshot_id=before_snapshot_id,
                        after_snapshot_id=after_snapshot_id,
                        document_id=mutated_document.id,
                        started_at=mutation_started_at,
                        completed_at=after_completed_at,
                    ),
                    output_artifact_ids=lambda result: [result.recommendation_id],
                )

                current_step = "recommendation_applied"
                await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="recommendation_applied",
                    fn=lambda: recommendation_repo.mark_applied(
                        session,
                        recommendation_id=primary_recommendation.id,
                        applied_at=after_completed_at,
                    ),
                    output_artifact_ids=[str(primary_recommendation.id)],
                )

                current_step = "review_gate"
                review_required, review_reason, review_session = await self._run_tracked_step(
                    pipeline_service=pipeline_service,
                    session=session,
                    execution_id=UUID(execution.id),
                    step_name="review_gate",
                    fn=lambda: self._run_review_gate(
                        review_service=review_service,
                        pipeline_service=pipeline_service,
                        session=session,
                        mutated_document_id=mutated_document.id,
                        user_id=user_id,
                        pipeline_execution_id=UUID(execution.id),
                        primary_task=primary_task,
                        before_evaluation=before_evaluation,
                        after_evaluation=after_evaluation,
                        after_tasks=after_tasks,
                    ),
                    output_artifact_ids=lambda result: [str(result[2].id)] if result[2] is not None else None,
                )

            artifacts = {
                "document_id": str(document_id),
                "mutated_document_id": str(mutated_document.id),
                "before_snapshot_id": str(before_snapshot_id),
                "after_snapshot_id": str(after_snapshot_id),
                "recommendation_id": str(primary_recommendation.id),
                "primary_task": self._task_payload(primary_task),
                "review_session_id": str(review_session.id) if review_session is not None else None,
                "trace": {
                    "trace_id": str(execution.id),
                    "correlation_id": get_trace_context().correlation_id,
                },
            }
            metrics = {
                "readiness_score": self._evaluation_payload(after_evaluation),
                "review_required": review_required,
                "impact": {
                    "readiness_delta": impact_measurement.readiness_delta.delta,
                    "time_to_complete_seconds": impact_measurement.time_to_complete_seconds,
                },
                "trace": {
                    "trace_id": str(execution.id),
                    "correlation_id": get_trace_context().correlation_id,
                },
            }

            current_step = "completion"
            await self._run_tracked_step(
                pipeline_service=pipeline_service,
                session=session,
                execution_id=UUID(execution.id),
                step_name="completion",
                fn=lambda: pipeline_service.complete_execution(
                    execution_id=UUID(execution.id),
                    artifacts=artifacts,
                    metrics=metrics,
                    resume_document_id=mutated_document.id,
                    review_required=review_required,
                    review_completed=False,
                    evaluation_duration_ms=int((before_completed_at - before_started_at).total_seconds() * 1000),
                    mutation_duration_ms=int((mutation_completed_at - mutation_started_at).total_seconds() * 1000),
                    session=session,
                ),
                output_artifact_ids=[str(mutated_document.id)],
            )
            await session.commit()

            logger.info(
                "Career pipeline completed",
                extra={
                    "execution_id": str(execution.id),
                    "document_id": str(mutated_document.id),
                    "review_required": review_required,
                },
            )

            return await pipeline_repo.get_execution(UUID(execution.id)) or execution

        except PipelineCancelledError:
            await session.rollback()
            logger.info(
                "Career pipeline cancelled",
                extra={"execution_id": str(execution.id)},
            )
            return await pipeline_repo.get_execution(UUID(execution.id)) or execution

        except Exception as exc:
            await session.rollback()
            error_message = str(exc)
            failed_step = current_step or "evaluation"
            retry_count = (execution.retry_count or 0) + 1
            failure_category = classify_failure(exc)
            retryable = is_retryable_failure(failure_category)

            await pipeline_service.fail_execution(
                execution_id=UUID(execution.id),
                error_code=type(exc).__name__,
                error_message=error_message,
                failed_step=failed_step,
                last_error=error_message,
                retry_count=retry_count,
                failure_category=failure_category.value,
                retryable=retryable,
                session=session,
            )
            await session.commit()
            logger.exception(
                "Career pipeline failed",
                extra={
                    "execution_id": str(execution.id),
                    "failed_step": failed_step,
                },
            )
            raise

    async def _run_tracked_step(
        self,
        *,
        pipeline_service: PipelineExecutionService,
        session: AsyncSession,
        execution_id: UUID,
        step_name: str,
        fn: Callable[[], Awaitable[T]],
        output_artifact_ids: list[str] | Callable[[T], list[str] | None] | None = None,
    ) -> T:
        if await pipeline_service.is_cancelled(execution_id):
            raise PipelineCancelledError(f"Pipeline execution {execution_id} was cancelled")

        step = await pipeline_service.start_step(
            execution_id=execution_id,
            step_name=step_name,
            session=session,
        )
        try:
            result = await fn()
            resolved_output_artifact_ids = (
                output_artifact_ids(result)
                if callable(output_artifact_ids)
                else output_artifact_ids
            )
            await pipeline_service.complete_step(
                step_id=UUID(str(step.id)),
                output_artifact_ids=resolved_output_artifact_ids,
                session=session,
            )
            return result
        except Exception as exc:
            await pipeline_service.fail_step(
                step_id=UUID(str(step.id)),
                error_message=str(exc),
                session=session,
            )
            raise

    async def _generate_and_persist_recommendations(
        self,
        *,
        recommendation_service: RecommendationTaskService,
        recommendation_repo: RecommendationRepository,
        session: AsyncSession,
        execution_id: UUID,
        document_id: UUID,
        readiness_score: ReadinessScore,
    ) -> tuple[list[RecommendationTask], RecommendationTask, list[Any]]:
        tasks = recommendation_service.prioritize_tasks(
            recommendation_service.generate_tasks_from_readiness(readiness_score)
        )
        primary_task = tasks[0] if tasks else self._build_fallback_task(readiness_score)
        recommendation_records = await recommendation_repo.create_recommendations(
            session,
            execution_id=execution_id,
            document_id=document_id,
            recommendations=[
                self._recommendation_payload(task)
                for task in tasks
            ] or [
                self._recommendation_payload(primary_task)
            ],
        )
        return tasks, primary_task, recommendation_records

    async def _apply_mutation(
        self,
        *,
        mutation_service: DocumentMutationService,
        session: AsyncSession,
        document_id: UUID,
        recommendation_id: UUID,
        changes: dict[str, Any],
        user_id: UUID,
    ) -> tuple[datetime, Any, datetime]:
        started_at = datetime.now(timezone.utc)
        mutated_document = await mutation_service.apply_recommendation(
            session=session,
            document_id=document_id,
            recommendation_id=recommendation_id,
            changes=changes,
            user_id=user_id,
        )
        completed_at = datetime.now(timezone.utc)
        return started_at, mutated_document, completed_at

    async def _run_review_gate(
        self,
        *,
        review_service: DocumentReviewService,
        pipeline_service: PipelineExecutionService,
        session: AsyncSession,
        mutated_document_id: UUID,
        user_id: UUID,
        pipeline_execution_id: UUID,
        primary_task: RecommendationTask,
        before_evaluation: Any,
        after_evaluation: Any,
        after_tasks: list[RecommendationTask],
    ) -> tuple[bool, str, Any | None]:
        review_required, review_reason = self._needs_review(after_evaluation, after_tasks)
        if not review_required:
            return review_required, review_reason, None

        review_session = await review_service.start_review(
            session,
            document_id=mutated_document_id,
            user_id=user_id,
            review_required=True,
            review_reason=review_reason,
            pipeline_execution_id=pipeline_execution_id,
            metadata={
                "primary_task": self._task_payload(primary_task),
                "readiness_before": self._evaluation_payload(before_evaluation),
                "readiness_after": self._evaluation_payload(after_evaluation),
            },
        )
        await pipeline_service.record_review_required(
            execution_id=pipeline_execution_id,
            review_reason=review_reason,
            session=session,
        )
        return review_required, review_reason, review_session

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

    def _recommendation_payload(self, task: RecommendationTask) -> dict[str, Any]:
        return {
            "category": task.task_type.value,
            "message": task.description or task.rationale,
            "estimated_score_improvement": task.estimated_score_improvement,
            "confidence": task.confidence,
        }

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
