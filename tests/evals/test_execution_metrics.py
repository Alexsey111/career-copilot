# tests/evals/test_execution_metrics.py

"""Tests for execution metrics and metrics aggregator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.domain.execution_metrics import (
    MetricTimeWindow,
    PipelineHealthStatus,
    DurationMetrics,
    SuccessRateMetrics,
    ReviewMetrics,
    FailureMetrics,
    RecommendationMetrics,
    ResumeSuccessMetrics,
    ExecutionMetrics,
    TrendMetrics,
)
from app.repositories.evaluation_snapshot_repository import (
    FailureMetricsAggregate,
    ReadinessDistribution,
    ResumeMetricsAggregate,
)
from app.repositories.pipeline_execution_repository import (
    PipelineDurationMetrics,
    PipelineFailureMetrics,
    PipelineSuccessMetrics,
)
from app.repositories.impact_measurement_repository import RecommendationImpactAggregate
from app.services.metrics_aggregator import MetricsAggregator


class TestDurationMetrics:
    """Tests for DurationMetrics."""

    def test_duration_metrics_creation(self):
        """Test creating duration metrics."""
        metrics = DurationMetrics(
            average_pipeline_duration_seconds=120.0,
            average_evaluation_duration_seconds=45.0,
            average_review_duration_seconds=300.0,
            p50_pipeline_duration_seconds=100.0,
            p90_pipeline_duration_seconds=200.0,
            sample_count=50,
        )

        assert metrics.average_pipeline_duration_seconds == 120.0
        assert metrics.sample_count == 50


class TestSuccessRateMetrics:
    """Tests for SuccessRateMetrics."""

    def test_success_rate_creation(self):
        """Test creating success rate metrics."""
        metrics = SuccessRateMetrics(
            completion_rate=0.85,
            failure_rate=0.10,
            success_rate=0.90,
            sample_count=100,
        )

        assert metrics.completion_rate == 0.85
        assert metrics.success_rate == 0.90


class TestReviewMetrics:
    """Tests for ReviewMetrics."""

    def test_review_metrics_creation(self):
        """Test creating review metrics."""
        metrics = ReviewMetrics(
            review_required_rate=0.25,
            review_approval_rate=0.80,
            average_review_duration_seconds=1800.0,
            sample_count=200,
        )

        assert metrics.review_required_rate == 0.25
        assert metrics.review_approval_rate == 0.80


class TestFailureMetrics:
    """Tests for FailureMetrics."""

    def test_failure_metrics_creation(self):
        """Test creating failure metrics."""
        metrics = FailureMetrics(
            critical_failure_rate=0.05,
            top_error_codes=[("TIMEOUT", 3), ("VALIDATION_ERROR", 2)],
            sample_count=100,
        )

        assert metrics.critical_failure_rate == 0.05
        assert len(metrics.top_error_codes) == 2


class TestRecommendationMetrics:
    """Tests for RecommendationMetrics."""

    def test_recommendation_metrics_creation(self):
        """Test creating recommendation metrics."""
        metrics = RecommendationMetrics(
            recommendation_completion_rate=0.60,
            average_time_to_complete_hours=24.0,
            average_readiness_improvement=0.12,
            recommendations_with_positive_impact_rate=0.75,
            sample_count=50,
        )

        assert metrics.recommendation_completion_rate == 0.60
        assert metrics.average_readiness_improvement == 0.12


class TestResumeSuccessMetrics:
    """Tests for ResumeSuccessMetrics."""

    def test_resume_success_metrics_creation(self):
        """Test creating resume success metrics."""
        metrics = ResumeSuccessMetrics(
            resume_success_rate=0.70,
            average_ats_score=0.75,
            average_evidence_score=0.68,
            average_coverage_score=0.80,
            ready_rate=0.50,
            needs_work_rate=0.30,
            not_ready_rate=0.20,
            sample_count=100,
        )

        assert metrics.resume_success_rate == 0.70
        assert metrics.ready_rate == 0.50


class TestExecutionMetrics:
    """Tests for ExecutionMetrics."""

    def test_execution_metrics_summary(self):
        """Test execution metrics summary."""
        metrics = ExecutionMetrics(
            time_window=MetricTimeWindow.LAST_7D,
            generated_at=datetime.now(),
            durations=DurationMetrics(
                average_pipeline_duration_seconds=120.0,
                average_evaluation_duration_seconds=45.0,
                average_review_duration_seconds=300.0,
                sample_count=100,
            ),
            success_rate=SuccessRateMetrics(
                completion_rate=0.85,
                failure_rate=0.10,
                success_rate=0.90,
                sample_count=100,
            ),
            reviews=ReviewMetrics(
                review_required_rate=0.25,
                review_approval_rate=0.80,
                average_review_duration_seconds=1800.0,
                sample_count=100,
            ),
            failures=FailureMetrics(
                critical_failure_rate=0.05,
                sample_count=100,
            ),
            recommendations=RecommendationMetrics(
                recommendation_completion_rate=0.60,
                average_time_to_complete_hours=24.0,
                sample_count=50,
            ),
            resumes=ResumeSuccessMetrics(
                resume_success_rate=0.70,
                average_ats_score=0.75,
                average_evidence_score=0.68,
                average_coverage_score=0.80,
                sample_count=100,
            ),
            total_executions=100,
        )

        summary = metrics.summary
        assert "last_7d" in summary
        assert "85.0%" in summary
        assert "health: healthy" in summary.lower()


class TestTrendMetrics:
    """Tests for TrendMetrics."""

    def test_trend_improving(self):
        """Test improving trend detection."""
        trend = TrendMetrics(
            metric_name="completion_rate",
            current_value=0.90,
            previous_value=0.80,
            delta=0.10,
            delta_percentage=12.5,
            direction="improving",
        )

        assert trend.is_improving is True

    def test_trend_degrading(self):
        """Test degrading trend detection."""
        trend = TrendMetrics(
            metric_name="failure_rate",
            current_value=0.15,
            previous_value=0.05,
            delta=0.10,
            delta_percentage=200.0,
            direction="degrading",
        )

        assert trend.is_improving is False


class TestMetricsAggregator:
    """Tests for MetricsAggregator."""

    @pytest.fixture
    def aggregator(self):
        pipeline_repo = AsyncMock()
        snapshot_repo = AsyncMock()
        impact_repo = AsyncMock()
        return (
            MetricsAggregator(pipeline_repo, snapshot_repo, impact_repo),
            pipeline_repo,
            snapshot_repo,
            impact_repo,
        )

    @pytest.mark.asyncio
    async def test_empty_aggregator(self, aggregator):
        """Test metrics with no data from repositories."""
        service, pipeline_repo, snapshot_repo, impact_repo = aggregator

        pipeline_repo.get_duration_metrics.return_value = PipelineDurationMetrics(
            count=0,
            avg_duration_ms=0.0,
            min_duration_ms=0.0,
            max_duration_ms=0.0,
            p50_duration_ms=0.0,
            p90_duration_ms=0.0,
        )
        pipeline_repo.get_success_metrics.return_value = PipelineSuccessMetrics(
            total_count=0,
            completed_count=0,
            failed_count=0,
            completion_rate=0.0,
            success_rate=0.0,
            failure_rate=0.0,
        )
        pipeline_repo.get_failure_metrics.return_value = PipelineFailureMetrics(
            total_count=0,
            failed_count=0,
            failure_rate=0.0,
            top_failure_codes=[],
        )
        snapshot_repo.get_resume_metrics.return_value = ResumeMetricsAggregate(
            count=0,
            avg_overall_score=0.0,
            avg_ats_score=0.0,
            avg_evidence_score=0.0,
            avg_coverage_score=0.0,
            avg_quality_score=0.0,
        )
        snapshot_repo.get_readiness_distribution.return_value = ReadinessDistribution(
            ready_count=0,
            ready_rate=0.0,
            needs_work_count=0,
            needs_work_rate=0.0,
            not_ready_count=0,
            not_ready_rate=0.0,
        )
        snapshot_repo.get_failure_metrics.return_value = FailureMetricsAggregate(
            total_count=0,
            critical_count=0,
            critical_failure_rate=0.0,
        )
        impact_repo.get_recommendation_impact_metrics.return_value = RecommendationImpactAggregate(
            completed_count=0,
            positive_impact_count=0,
            average_readiness_improvement=0.0,
            completion_count_by_type={},
        )

        metrics = await service.get_metrics(AsyncMock(), MetricTimeWindow.ALL_TIME)

        assert metrics.success_rate.completion_rate == 0.0
        assert metrics.success_rate.failure_rate == 0.0
        assert metrics.durations.sample_count == 0

    @pytest.mark.asyncio
    async def test_recommendation_metrics(self, aggregator):
        """Test recommendation metrics composition from measurements."""
        service, pipeline_repo, snapshot_repo, impact_repo = aggregator
        pipeline_repo.get_duration_metrics.return_value = PipelineDurationMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0)
        pipeline_repo.get_success_metrics.return_value = PipelineSuccessMetrics(10, 9, 1, 0.9, 0.9, 0.1)
        pipeline_repo.get_failure_metrics.return_value = PipelineFailureMetrics(10, 1, 0.1, [("TIMEOUT", 1)])
        snapshot_repo.get_resume_metrics.return_value = ResumeMetricsAggregate(10, 0.7, 0.75, 0.68, 0.8, 0.7)
        snapshot_repo.get_readiness_distribution.return_value = ReadinessDistribution(6, 0.6, 3, 0.3, 1, 0.1)
        snapshot_repo.get_failure_metrics.return_value = FailureMetricsAggregate(10, 1, 0.1)
        impact_repo.get_recommendation_impact_metrics.return_value = RecommendationImpactAggregate(
            completed_count=3,
            positive_impact_count=1,
            average_readiness_improvement=0.016666666666666666,
            completion_count_by_type={"rec": 3},
        )

        metrics = await service.get_metrics(AsyncMock(), MetricTimeWindow.LAST_7D)
        assert metrics.recommendations.recommendation_completion_rate == 1.0
        assert metrics.recommendations.sample_count == 3
        assert metrics.recommendations.recommendations_with_positive_impact_rate == 1 / 3

    @pytest.mark.asyncio
    async def test_health_status_warning(self, aggregator):
        """Test warning status with elevated failure rate."""
        service, pipeline_repo, snapshot_repo, impact_repo = aggregator

        pipeline_repo.get_duration_metrics.return_value = PipelineDurationMetrics(100, 120000.0, 60000.0, 240000.0, 120000.0, 180000.0)
        pipeline_repo.get_success_metrics.return_value = PipelineSuccessMetrics(100, 90, 10, 0.9, 0.9, 0.1)
        pipeline_repo.get_failure_metrics.return_value = PipelineFailureMetrics(100, 10, 0.1, [("TIMEOUT", 10)])
        snapshot_repo.get_resume_metrics.return_value = ResumeMetricsAggregate(100, 0.7, 0.75, 0.68, 0.8, 0.7)
        snapshot_repo.get_readiness_distribution.return_value = ReadinessDistribution(60, 0.6, 30, 0.3, 10, 0.1)
        snapshot_repo.get_failure_metrics.return_value = FailureMetricsAggregate(100, 10, 0.1)
        impact_repo.get_recommendation_impact_metrics.return_value = RecommendationImpactAggregate(
            completed_count=0,
            positive_impact_count=0,
            average_readiness_improvement=0.0,
            completion_count_by_type={},
        )

        metrics = await service.get_metrics(AsyncMock(), MetricTimeWindow.ALL_TIME)
        assert metrics.health_status == PipelineHealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_health_status_critical(self, aggregator):
        """Test critical status with high failure rate."""
        service, pipeline_repo, snapshot_repo, impact_repo = aggregator

        pipeline_repo.get_duration_metrics.return_value = PipelineDurationMetrics(100, 120000.0, 60000.0, 240000.0, 120000.0, 180000.0)
        pipeline_repo.get_success_metrics.return_value = PipelineSuccessMetrics(100, 60, 40, 0.6, 0.6, 0.4)
        pipeline_repo.get_failure_metrics.return_value = PipelineFailureMetrics(100, 40, 0.4, [("TIMEOUT", 40)])
        snapshot_repo.get_resume_metrics.return_value = ResumeMetricsAggregate(100, 0.5, 0.55, 0.5, 0.6, 0.5)
        snapshot_repo.get_readiness_distribution.return_value = ReadinessDistribution(30, 0.3, 30, 0.3, 40, 0.4)
        snapshot_repo.get_failure_metrics.return_value = FailureMetricsAggregate(100, 40, 0.4)
        impact_repo.get_recommendation_impact_metrics.return_value = RecommendationImpactAggregate(
            completed_count=0,
            positive_impact_count=0,
            average_readiness_improvement=0.0,
            completion_count_by_type={},
        )

        metrics = await service.get_metrics(AsyncMock(), MetricTimeWindow.ALL_TIME)
        assert metrics.health_status == PipelineHealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_time_window_filtering(self, aggregator):
        """Test that measurement time window filtering works."""
        service, pipeline_repo, snapshot_repo, impact_repo = aggregator
        pipeline_repo.get_duration_metrics.return_value = PipelineDurationMetrics(2, 0.0, 0.0, 0.0, 0.0, 0.0)
        pipeline_repo.get_success_metrics.return_value = PipelineSuccessMetrics(2, 2, 0, 1.0, 1.0, 0.0)
        pipeline_repo.get_failure_metrics.return_value = PipelineFailureMetrics(2, 0, 0.0, [])
        snapshot_repo.get_resume_metrics.return_value = ResumeMetricsAggregate(2, 0.8, 0.8, 0.8, 0.8, 0.8)
        snapshot_repo.get_readiness_distribution.return_value = ReadinessDistribution(2, 1.0, 0, 0.0, 0, 0.0)
        snapshot_repo.get_failure_metrics.return_value = FailureMetricsAggregate(2, 0, 0.0)
        impact_repo.get_recommendation_impact_metrics.side_effect = [
            RecommendationImpactAggregate(
                completed_count=1,
                positive_impact_count=1,
                average_readiness_improvement=0.1,
                completion_count_by_type={"recent": 1},
            ),
            RecommendationImpactAggregate(
                completed_count=2,
                positive_impact_count=2,
                average_readiness_improvement=0.15,
                completion_count_by_type={"old": 1, "recent": 1},
            ),
        ]

        metrics_24h = await service.get_metrics(AsyncMock(), MetricTimeWindow.LAST_24H)
        assert metrics_24h.recommendations.sample_count == 1

        metrics_7d = await service.get_metrics(AsyncMock(), MetricTimeWindow.LAST_7D)
        assert metrics_7d.recommendations.sample_count == 2

    @pytest.mark.asyncio
    async def test_trend_calculation(self, aggregator):
        """Test trend calculation."""
        service, _, _, _ = aggregator
        current = ExecutionMetrics(
            time_window=MetricTimeWindow.LAST_7D,
            generated_at=datetime.now(),
            durations=DurationMetrics(
                average_pipeline_duration_seconds=120.0,
                average_evaluation_duration_seconds=45.0,
                average_review_duration_seconds=300.0,
                sample_count=100,
            ),
            success_rate=SuccessRateMetrics(
                completion_rate=0.90,
                failure_rate=0.05,
                success_rate=0.95,
                sample_count=100,
            ),
            reviews=ReviewMetrics(
                review_required_rate=0.20,
                review_approval_rate=0.85,
                average_review_duration_seconds=1800.0,
                sample_count=100,
            ),
            failures=FailureMetrics(
                critical_failure_rate=0.05,
                sample_count=100,
            ),
            recommendations=RecommendationMetrics(
                recommendation_completion_rate=0.65,
                average_time_to_complete_hours=24.0,
                sample_count=50,
            ),
            resumes=ResumeSuccessMetrics(
                resume_success_rate=0.75,
                average_ats_score=0.78,
                average_evidence_score=0.70,
                average_coverage_score=0.82,
                sample_count=100,
            ),
            total_executions=100,
        )

        previous = ExecutionMetrics(
            time_window=MetricTimeWindow.LAST_30D,
            generated_at=datetime.now() - timedelta(days=7),
            durations=DurationMetrics(
                average_pipeline_duration_seconds=150.0,
                average_evaluation_duration_seconds=50.0,
                average_review_duration_seconds=300.0,
                sample_count=400,
            ),
            success_rate=SuccessRateMetrics(
                completion_rate=0.80,
                failure_rate=0.15,
                success_rate=0.85,
                sample_count=400,
            ),
            reviews=ReviewMetrics(
                review_required_rate=0.25,
                review_approval_rate=0.80,
                average_review_duration_seconds=1800.0,
                sample_count=400,
            ),
            failures=FailureMetrics(
                critical_failure_rate=0.15,
                sample_count=400,
            ),
            recommendations=RecommendationMetrics(
                recommendation_completion_rate=0.55,
                average_time_to_complete_hours=30.0,
                sample_count=200,
            ),
            resumes=ResumeSuccessMetrics(
                resume_success_rate=0.65,
                average_ats_score=0.72,
                average_evidence_score=0.65,
                average_coverage_score=0.75,
                sample_count=400,
            ),
            total_executions=400,
        )

        trend = await service.get_trend(AsyncMock(), "completion_rate", current, previous)

        assert trend.metric_name == "completion_rate"
        assert trend.current_value == 0.90
        assert trend.previous_value == 0.80
        assert abs(trend.delta - 0.10) < 0.001
        assert trend.direction == "improving"
