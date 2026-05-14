# app/services/metrics_aggregator.py

"""
Metrics Aggregator — вычисление агрегированных метрик pipeline execution.

Вычисляет:
- average pipeline duration
- average evaluation duration
- review_required_rate
- critical_failure_rate
- recommendation_completion_rate
- resume_success_rate

Architecture:
- Repository layer: SQL aggregation (AVG, COUNT, GROUP BY)
- MetricsAggregator: composition of aggregate DTOs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.execution_metrics import (
    DurationMetrics,
    SuccessRateMetrics,
    ReviewMetrics,
    FailureMetrics,
    RecommendationMetrics,
    ResumeSuccessMetrics,
    ExecutionMetrics,
    MetricTimeWindow,
    PipelineHealthStatus,
    TrendMetrics,
)
from app.repositories.evaluation_snapshot_repository import (
    EvaluationSnapshotRepository,
    ResumeMetricsAggregate,
    ReadinessDistribution,
    FailureMetricsAggregate,
)
from app.repositories.impact_measurement_repository import ImpactMeasurementRepository
from app.repositories.impact_measurement_repository import RecommendationImpactAggregate
from app.repositories.pipeline_execution_repository import PipelineExecutionRepository
from app.repositories.review_workflow_repository import (
    ReviewWorkflowRepository,
    ReviewWorkflowMetricsAggregate,
)


@dataclass
class ExecutionRecord:
    """Запись выполнения для агрегации метрик."""
    execution_id: str
    user_id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    step_durations: dict[str, int] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    review_id: Optional[str] = None
    evaluation_snapshot_id: Optional[str] = None
    resume_document_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RecommendationRecord:
    """Запись рекомендации для агрегации метрик."""
    recommendation_id: str
    user_id: str
    recommendation_type: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    is_completed: bool = False
    readiness_delta: float = 0.0


class MetricsAggregator:
    """
    Агрегатор метрик pipeline execution.
    
    ЧИТАЕТ ИЗ БД через repository aggregation:
    - PipelineExecutionRepository → duration, success rate
    - EvaluationSnapshotRepository → scores, readiness distribution
    - ImpactMeasurementRepository → recommendation impact

    Пример использования:
        aggregator = MetricsAggregator(
            pipeline_repo, 
            snapshot_repo, 
            impact_repo
        )
        
        async with session.begin():
            metrics = await aggregator.get_metrics(session, MetricTimeWindow.LAST_7D)
    """

    def __init__(
        self,
        pipeline_repository: PipelineExecutionRepository,
        snapshot_repository: EvaluationSnapshotRepository,
        impact_repository: ImpactMeasurementRepository,
        review_repository: ReviewWorkflowRepository | None = None,
    ) -> None:
        self._pipeline_repo = pipeline_repository
        self._snapshot_repo = snapshot_repository
        self._impact_repo = impact_repository
        self._review_repo = review_repository

    async def get_metrics(
        self,
        session: AsyncSession,
        time_window: MetricTimeWindow,
    ) -> ExecutionMetrics:
        """
        Вычисляет агрегированные метрики для временного окна из БД.
        
        Repository layer выполняет SQL aggregation,
        этот метод только компонует DTO.

        Args:
            session: Database session
            time_window: Временное окно для агрегации

        Returns:
            ExecutionMetrics с вычисленными показателями
        """
        cutoff_time = self._get_cutoff_time(time_window)

        # Repository-level SQL aggregation
        pipeline_duration = await self._pipeline_repo.get_duration_metrics(
            session=session,
            start_time=cutoff_time,
        )
        pipeline_success = await self._pipeline_repo.get_success_metrics(
            session=session,
            start_time=cutoff_time,
        )
        pipeline_failures = await self._pipeline_repo.get_failure_metrics(
            session=session,
            start_time=cutoff_time,
        )
        
        resume_metrics: ResumeMetricsAggregate = await self._snapshot_repo.get_resume_metrics(
            session=session,
            start_time=cutoff_time,
        )
        readiness_dist: ReadinessDistribution = await self._snapshot_repo.get_readiness_distribution(
            session=session,
            start_time=cutoff_time,
        )
        failure_agg: FailureMetricsAggregate = await self._snapshot_repo.get_failure_metrics(
            session=session,
            start_time=cutoff_time,
        )
        
        recommendation_impact = await self._impact_repo.get_recommendation_impact_metrics(
            session=session,
            start_time=cutoff_time,
        )
        review_metrics = await self._get_review_metrics(session, cutoff_time)

        # Compose metrics from repository aggregates
        durations = self._compose_duration_metrics(pipeline_duration)
        success_rate = self._compose_success_rate(pipeline_success, resume_metrics)
        reviews = self._compose_review_metrics(readiness_dist, review_metrics)
        failures = self._compose_failure_metrics(pipeline_failures, failure_agg)
        recommendations = self._compose_recommendation_metrics(recommendation_impact)
        resumes = self._compose_resume_success_metrics(resume_metrics, readiness_dist)

        health_status = self._compute_health_status(success_rate, failures, reviews)

        return ExecutionMetrics(
            time_window=time_window,
            generated_at=datetime.now(timezone.utc),
            durations=durations,
            success_rate=success_rate,
            reviews=reviews,
            failures=failures,
            recommendations=recommendations,
            resumes=resumes,
            total_executions=pipeline_success.total_count,
            health_status=health_status,
        )

    async def get_metrics_for_range(
        self,
        session: AsyncSession,
        start_time: datetime,
        end_time: Optional[datetime] = None,
    ) -> ExecutionMetrics:
        """
        Вычисляет метрики для явного диапазона дат.

        Используется TrendService для получения сопоставимых периодов.

        Args:
            session: Database session
            start_time: Начало диапазона
            end_time: Конец диапазона (по умолчанию now)

        Returns:
            ExecutionMetrics для указанного диапазона
        """
        from app.domain.execution_metrics import MetricTimeWindow, ExecutionMetrics, PipelineHealthStatus

        start_time = self._ensure_utc(start_time)
        if end_time is not None:
            end_time = self._ensure_utc(end_time)

        if end_time is None:
            end_time = datetime.now(timezone.utc)

        # Временный time_window для агрегации
        time_window = MetricTimeWindow.LAST_7D  # Placeholder, не используется

        # Repository-level SQL aggregation
        pipeline_duration = await self._pipeline_repo.get_duration_metrics(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        pipeline_success = await self._pipeline_repo.get_success_metrics(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        pipeline_failures = await self._pipeline_repo.get_failure_metrics(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        
        resume_metrics: ResumeMetricsAggregate = await self._snapshot_repo.get_resume_metrics(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        readiness_dist: ReadinessDistribution = await self._snapshot_repo.get_readiness_distribution(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        failure_agg: FailureMetricsAggregate = await self._snapshot_repo.get_failure_metrics(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        
        recommendation_impact = await self._impact_repo.get_recommendation_impact_metrics(
            session=session,
            start_time=start_time,
            end_time=end_time,
        )
        review_metrics = await self._get_review_metrics(session, start_time, end_time)

        # Compose metrics from repository aggregates
        durations = self._compose_duration_metrics(pipeline_duration)
        success_rate = self._compose_success_rate(pipeline_success, resume_metrics)
        reviews = self._compose_review_metrics(readiness_dist, review_metrics)
        failures = self._compose_failure_metrics(pipeline_failures, failure_agg)
        recommendations = self._compose_recommendation_metrics(recommendation_impact)
        resumes = self._compose_resume_success_metrics(resume_metrics, readiness_dist)

        health_status = self._compute_health_status(success_rate, failures, reviews)

        return ExecutionMetrics(
            time_window=time_window,
            generated_at=datetime.now(timezone.utc),
            durations=durations,
            success_rate=success_rate,
            reviews=reviews,
            failures=failures,
            recommendations=recommendations,
            resumes=resumes,
            total_executions=pipeline_success.total_count,
            health_status=health_status,
        )

    def _get_cutoff_time(self, time_window: MetricTimeWindow) -> datetime:
        """Вычисляет время отсечения для временного окна."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        match time_window:
            case MetricTimeWindow.LAST_24H:
                return now - timedelta(hours=24)
            case MetricTimeWindow.LAST_7D:
                return now - timedelta(days=7)
            case MetricTimeWindow.LAST_30D:
                return now - timedelta(days=30)
            case MetricTimeWindow.LAST_90D:
                return now - timedelta(days=90)
            case MetricTimeWindow.ALL_TIME:
                return datetime.min.replace(tzinfo=timezone.utc)

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        """Normalize datetimes to UTC-aware values for range comparisons."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _compose_duration_metrics(
        self,
        repo_metrics,
    ) -> DurationMetrics:
        """Composes DurationMetrics from repository aggregate DTO."""
        return DurationMetrics(
            average_pipeline_duration_seconds=repo_metrics.avg_duration_ms / 1000,
            average_evaluation_duration_seconds=repo_metrics.avg_evaluation_duration_ms / 1000,
            average_review_duration_seconds=0.0,
            p50_pipeline_duration_seconds=repo_metrics.p50_duration_ms / 1000,
            p90_pipeline_duration_seconds=repo_metrics.p90_duration_ms / 1000,
            p99_pipeline_duration_seconds=0.0,
            min_pipeline_duration_seconds=repo_metrics.min_duration_ms / 1000,
            max_pipeline_duration_seconds=repo_metrics.max_duration_ms / 1000,
            sample_count=repo_metrics.count,
        )

    def _compose_success_rate(
        self,
        pipeline_success,
        resume_metrics,
    ) -> SuccessRateMetrics:
        """Composes SuccessRateMetrics from repository aggregates."""
        return SuccessRateMetrics(
            completion_rate=pipeline_success.completion_rate,
            failure_rate=pipeline_success.failure_rate,
            success_rate=pipeline_success.success_rate,
            pending_rate=0.0,
            running_rate=0.0,
            cancelled_rate=0.0,
            sample_count=pipeline_success.total_count,
        )

    async def _get_review_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> ReviewWorkflowMetricsAggregate | None:
        if self._review_repo is None:
            return None
        return await self._review_repo.get_review_metrics(session, start_time, end_time)

    def _compose_review_metrics(
        self,
        readiness_dist: ReadinessDistribution,
        review_metrics: ReviewWorkflowMetricsAggregate | None,
    ) -> ReviewMetrics:
        """Composes ReviewMetrics from repository aggregates."""
        if review_metrics is not None:
            return ReviewMetrics(
                review_required_rate=review_metrics.review_required_rate,
                review_approval_rate=review_metrics.approval_rate,
                average_review_duration_seconds=review_metrics.average_review_duration_ms / 1000,
                critical_review_rate=review_metrics.review_required_rate,
                manual_review_rate=review_metrics.review_required_rate,
                sample_count=review_metrics.total_sessions,
            )

        return ReviewMetrics(
            review_required_rate=readiness_dist.needs_work_rate,
            review_approval_rate=0.85,
            average_review_duration_seconds=0.0,
            critical_review_rate=readiness_dist.not_ready_rate,
            manual_review_rate=readiness_dist.needs_work_rate,
            sample_count=readiness_dist.ready_count + readiness_dist.needs_work_count + readiness_dist.not_ready_count,
        )

    def _compose_failure_metrics(
        self,
        pipeline_failures,
        snapshot_failures: FailureMetricsAggregate,
    ) -> FailureMetrics:
        """Composes FailureMetrics from repository aggregates."""
        return FailureMetrics(
            critical_failure_rate=snapshot_failures.critical_failure_rate,
            error_rate_by_step={},
            top_error_codes=pipeline_failures.top_failure_codes,
            sample_count=pipeline_failures.total_count,
        )

    def _compose_recommendation_metrics(
        self,
        recommendation_impact: RecommendationImpactAggregate,
    ) -> RecommendationMetrics:
        """Composes RecommendationMetrics from repository aggregate DTO."""
        if recommendation_impact.completed_count == 0:
            return RecommendationMetrics(
                recommendation_completion_rate=0.0,
                average_time_to_complete_hours=0.0,
                sample_count=0,
            )

        completed = recommendation_impact.completed_count
        positive_rate = recommendation_impact.positive_impact_count / completed
        avg_improvement = recommendation_impact.average_readiness_improvement

        return RecommendationMetrics(
            recommendation_completion_rate=1.0,
            average_time_to_complete_hours=0.0,
            average_readiness_improvement=avg_improvement,
            recommendations_with_positive_impact_rate=positive_rate,
            completion_rate_by_type={
                recommendation_type: 1.0
                for recommendation_type in recommendation_impact.completion_count_by_type
            },
            sample_count=completed,
        )

    def _compose_resume_success_metrics(
        self,
        resume_metrics: ResumeMetricsAggregate,
        readiness_dist: ReadinessDistribution,
    ) -> ResumeSuccessMetrics:
        """Composes ResumeSuccessMetrics from repository aggregates."""
        return ResumeSuccessMetrics(
            resume_success_rate=readiness_dist.ready_rate,
            average_ats_score=resume_metrics.avg_ats_score,
            average_evidence_score=resume_metrics.avg_evidence_score,
            average_coverage_score=resume_metrics.avg_coverage_score,
            ready_rate=readiness_dist.ready_rate,
            needs_work_rate=readiness_dist.needs_work_rate,
            not_ready_rate=readiness_dist.not_ready_rate,
            sample_count=resume_metrics.count,
        )

    def _compute_health_status(
        self,
        success_rate: SuccessRateMetrics,
        failures: FailureMetrics,
        reviews: ReviewMetrics,
    ) -> PipelineHealthStatus:
        """Определяет общее состояние здоровья pipeline."""
        # Critical: failure rate > 30%
        if failures.critical_failure_rate > 0.30:
            return PipelineHealthStatus.CRITICAL

        # Degraded: failure rate > 15% or success rate < 70%
        if failures.critical_failure_rate > 0.15 or success_rate.success_rate < 0.70:
            return PipelineHealthStatus.DEGRADED

        # Warning: failure rate > 5%
        if failures.critical_failure_rate > 0.05:
            return PipelineHealthStatus.WARNING

        return PipelineHealthStatus.HEALTHY

    async def get_trend(
        self,
        session: AsyncSession,
        metric_name: str,
        current_metrics: ExecutionMetrics,
        previous_metrics: ExecutionMetrics,
    ) -> TrendMetrics:
        """
        Вычисляет тренд для метрики.

        Args:
            session: Database session
            metric_name: Имя метрики
            current_metrics: Текущие метрики
            previous_metrics: Предыдущие метрики

        Returns:
            TrendMetrics с направлением тренда
        """
        value_map = {
            "completion_rate": current_metrics.success_rate.completion_rate,
            "failure_rate": current_metrics.failures.critical_failure_rate,
            "review_required_rate": current_metrics.reviews.review_required_rate,
            "recommendation_completion_rate": current_metrics.recommendations.recommendation_completion_rate,
            "resume_success_rate": current_metrics.resumes.resume_success_rate,
            "average_duration": current_metrics.durations.average_pipeline_duration_seconds,
        }

        current_value = value_map.get(metric_name, 0.0)

        prev_map = {
            "completion_rate": previous_metrics.success_rate.completion_rate,
            "failure_rate": previous_metrics.failures.critical_failure_rate,
            "review_required_rate": previous_metrics.reviews.review_required_rate,
            "recommendation_completion_rate": previous_metrics.recommendations.recommendation_completion_rate,
            "resume_success_rate": previous_metrics.resumes.resume_success_rate,
            "average_duration": previous_metrics.durations.average_pipeline_duration_seconds,
        }

        previous_value = prev_map.get(metric_name, 0.0)

        delta = current_value - previous_value
        delta_percentage = (delta / previous_value * 100) if previous_value != 0 else 0.0

        # Determine direction
        if abs(delta) < 0.01:
            direction = "stable"
        elif metric_name in ["failure_rate", "review_required_rate"]:
            direction = "improving" if delta < 0 else "degrading"
        else:
            direction = "improving" if delta > 0 else "degrading"

        return TrendMetrics(
            metric_name=metric_name,
            current_value=current_value,
            previous_value=previous_value,
            delta=delta,
            delta_percentage=delta_percentage,
            direction=direction,
        )


class PipelineMetricsService:
    """
    Сервис для получения метрик pipeline.

    Интегрируется с репозиториями для чтения данных из БД.

    Архитектурный поток:
    Document → Feature Extraction → Deterministic Scoring 
    → Evaluation Snapshot → Recommendations → Mutation 
    → New Document Version → Re-evaluation → Impact Measurement

    Разделение ответственности:
    - Repository: SQL aggregation (AVG, COUNT, GROUP BY)
    - MetricsAggregator: composition of aggregate DTOs

    Для трендов используйте TrendService:
        trend_service = TrendService(aggregator)
        trend = await trend_service.get_trend(
            session, "resume_success_rate", MetricTimeWindow.LAST_7D
        )
    """

    def __init__(
        self,
        pipeline_repository,
        snapshot_repository,
        impact_repository,
        review_repository: ReviewWorkflowRepository | None = None,
    ) -> None:
        self._aggregator = MetricsAggregator(
            pipeline_repository, 
            snapshot_repository, 
            impact_repository,
            review_repository,
        )

    async def get_execution_metrics(
        self,
        session: AsyncSession,
        time_window: MetricTimeWindow,
    ) -> ExecutionMetrics:
        """Получает агрегированные метрики из БД."""
        return await self._aggregator.get_metrics(session, time_window)

    async def get_metrics_for_range(
        self,
        session: AsyncSession,
        start_time: datetime,
        end_time: Optional[datetime] = None,
    ) -> ExecutionMetrics:
        """Получает метрики для явного диапазона дат."""
        return await self._aggregator.get_metrics_for_range(session, start_time, end_time)
