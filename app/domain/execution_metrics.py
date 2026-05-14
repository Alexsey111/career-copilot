# app/domain/execution_metrics.py

"""
Execution Metrics — агрегированные метрики pipeline execution.

Позволяет ответить:
- Какова средняя длительность pipeline?
- Как часто требуется review?
- Какой процент критических сбоев?
- Насколько эффективны рекомендации?
- Какой успех у resume generation?

Это делает platform behavior observable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MetricTimeWindow(Enum):
    """Временные окна для агрегации метрик."""
    LAST_24H = "last_24h"
    LAST_7D = "last_7d"
    LAST_30D = "last_30d"
    LAST_90D = "last_90d"
    ALL_TIME = "all_time"


class PipelineHealthStatus(Enum):
    """Уровень здоровья pipeline."""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass(slots=True)
class DurationMetrics:
    """Метрики длительности выполнения."""
    average_pipeline_duration_seconds: float
    average_evaluation_duration_seconds: float
    average_review_duration_seconds: float

    # Percentiles
    p50_pipeline_duration_seconds: float = 0.0
    p90_pipeline_duration_seconds: float = 0.0
    p99_pipeline_duration_seconds: float = 0.0

    # Min/Max
    min_pipeline_duration_seconds: float = 0.0
    max_pipeline_duration_seconds: float = 0.0

    # Sample size
    sample_count: int = 0


@dataclass(slots=True)
class SuccessRateMetrics:
    """Метрики успеха pipeline."""
    completion_rate: float  # % completed / total
    failure_rate: float  # % failed / total
    success_rate: float  # 1 - failure_rate

    # Breakdown by status
    pending_rate: float = 0.0
    running_rate: float = 0.0
    cancelled_rate: float = 0.0

    # Sample size
    sample_count: int = 0


@dataclass(slots=True)
class ReviewMetrics:
    """Метрики review процесса."""
    review_required_rate: float  # % requiring review
    review_approval_rate: float  # % approved / reviewed
    average_review_duration_seconds: float

    # Breakdown
    critical_review_rate: float = 0.0  # % with critical issues
    manual_review_rate: float = 0.0  # % requiring manual intervention

    # Sample size
    sample_count: int = 0


@dataclass(slots=True)
class FailureMetrics:
    """Метрики сбоев."""
    critical_failure_rate: float  # % with critical failures
    error_rate_by_step: dict[str, float] = field(default_factory=dict)

    # Common error patterns
    top_error_codes: list[tuple[str, int]] = field(default_factory=list)

    # Sample size
    sample_count: int = 0


@dataclass(slots=True)
class RecommendationMetrics:
    """Метрики рекомендаций."""
    recommendation_completion_rate: float  # % completed / issued
    average_time_to_complete_hours: float

    # Impact metrics
    average_readiness_improvement: float = 0.0
    recommendations_with_positive_impact_rate: float = 0.0

    # Breakdown by type
    completion_rate_by_type: dict[str, float] = field(default_factory=dict)

    # Sample size
    sample_count: int = 0


@dataclass(slots=True)
class ResumeSuccessMetrics:
    """Метрики успеха resume generation."""
    resume_success_rate: float  # % successful generations
    average_ats_score: float
    average_evidence_score: float
    average_coverage_score: float

    # Readiness distribution
    ready_rate: float = 0.0  # % with is_ready=True
    needs_work_rate: float = 0.0  # % needs_work
    not_ready_rate: float = 0.0  # % not_ready

    # Sample size
    sample_count: int = 0


@dataclass(slots=True)
class UserEngagementMetrics:
    """Метрики вовлеченности пользователей."""
    active_users_count: int
    executions_per_user: float
    recommendations_per_user: float
    review_sessions_per_user: float


@dataclass(slots=True)
class ExecutionMetrics:
    """
    Полные метрики выполнения pipeline.

    Пример использования:
        metrics = ExecutionMetrics(
            time_window=MetricTimeWindow.LAST_7D,
            generated_at=datetime.now(timezone.utc),
        )

        print(f"Completion rate: {metrics.success_rate.completion_rate:.1%}")
        print(f"Critical failures: {metrics.failures.critical_failure_rate:.1%}")
    """
    time_window: MetricTimeWindow
    generated_at: datetime

    # Core metrics
    durations: DurationMetrics
    success_rate: SuccessRateMetrics

    # Quality metrics
    reviews: ReviewMetrics
    failures: FailureMetrics

    # Recommendation effectiveness
    recommendations: RecommendationMetrics

    # Resume quality
    resumes: ResumeSuccessMetrics

    # Engagement
    engagement: Optional[UserEngagementMetrics] = None

    # Overall health
    health_status: PipelineHealthStatus = PipelineHealthStatus.HEALTHY

    # Sample counts
    total_executions: int = 0

    @property
    def summary(self) -> str:
        """Краткая сводка метрик."""
        return (
            f"Execution Metrics ({self.time_window.value}):\n"
            f"  Completions: {self.success_rate.completion_rate:.1%} "
            f"(n={self.success_rate.sample_count})\n"
            f"  Critical Failures: {self.failures.critical_failure_rate:.1%}\n"
            f"  Review Required: {self.reviews.review_required_rate:.1%}\n"
            f"  Avg Duration: {self.durations.average_pipeline_duration_seconds/60:.1f} min\n"
            f"  Health: {self.health_status.value}"
        )


@dataclass(slots=True)
class TrendMetrics:
    """
    Метрики трендов во времени.

    Позволяет отслеживать улучшение/ухудшение платформы.
    """
    metric_name: str
    current_value: float
    previous_value: float
    delta: float
    delta_percentage: float

    # Trend direction
    direction: str  # "improving", "stable", "degrading"

    # Historical data points
    data_points: list[tuple[datetime, float]] = field(default_factory=list)

    @property
    def is_improving(self) -> bool:
        """Проверяет, улучшается ли метрика."""
        return self.direction == "improving"
