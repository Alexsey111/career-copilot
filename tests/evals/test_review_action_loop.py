# tests/evals/test_review_action_loop.py

"""Tests for Review Action Loop."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.services.review_action_loop import (
    ReadinessDelta,
    RecommendationImpactMeasurement,
    RecommendationExecutionStatus,
    ImpactReport,
    format_impact_message,
)


class TestReadinessDelta:
    """Tests for ReadinessDelta."""

    def test_improvement(self):
        """Test positive delta detection."""
        delta = ReadinessDelta(
            before_overall=0.60,
            after_overall=0.75,
            delta=0.15,
        )

        assert delta.improvement is True

    def test_decline(self):
        """Test negative delta detection."""
        delta = ReadinessDelta(
            before_overall=0.80,
            after_overall=0.70,
            delta=-0.10,
        )

        assert delta.improvement is False

    def test_no_change(self):
        """Test zero delta."""
        delta = ReadinessDelta(
            before_overall=0.70,
            after_overall=0.70,
            delta=0.0,
        )

        assert delta.improvement is False

    def test_improvement_percentage(self):
        """Test improvement percentage calculation."""
        delta = ReadinessDelta(
            before_overall=0.50,
            after_overall=0.75,
            delta=0.25,
        )

        assert delta.improvement_percentage == 50.0

    def test_improvement_percentage_zero_base(self):
        """Test improvement percentage with zero base."""
        delta = ReadinessDelta(
            before_overall=0.0,
            after_overall=0.50,
            delta=0.50,
        )

        assert delta.improvement_percentage == 0.0

    def test_component_deltas(self):
        """Test component-level delta calculation."""
        delta = ReadinessDelta(
            before_overall=0.60,
            after_overall=0.75,
            delta=0.15,
            before_components={"ats": 0.5, "evidence": 0.6},
            after_components={"ats": 0.7, "evidence": 0.7},
            component_deltas={"ats": 0.2, "evidence": 0.1},
        )

        assert delta.component_deltas["ats"] == 0.2
        assert delta.component_deltas["evidence"] == 0.1


class TestRecommendationImpactMeasurement:
    """Tests for RecommendationImpactMeasurement."""

    def test_completed_measurement(self):
        """Test creating completed measurement."""
        measurement = RecommendationImpactMeasurement(
            recommendation_id="rec-123",
            recommendation_type="add_metric",
            target_achievement_id="ach-1",
            execution_status=RecommendationExecutionStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            changes_made=["added metric to achievement"],
        )

        assert measurement.recommendation_id == "rec-123"
        assert measurement.execution_status == RecommendationExecutionStatus.COMPLETED
        assert len(measurement.changes_made) == 1


class TestImpactReport:
    """Tests for ImpactReport."""

    def test_positive_impact_summary(self):
        """Test impact summary for positive change."""
        report = ImpactReport(
            recommendation_id="rec-123",
            description="Added metric to achievement",
            readiness_before=0.62,
            readiness_after=0.74,
            readiness_delta=0.12,
            completed_at=datetime.now(),
        )

        assert "0.62" in report.impact_summary
        assert "0.74" in report.impact_summary
        assert "+0.12" in report.impact_summary

    def test_negative_impact_summary(self):
        """Test impact summary for negative change."""
        report = ImpactReport(
            recommendation_id="rec-123",
            description="Removed redundant content",
            readiness_before=0.80,
            readiness_after=0.75,
            readiness_delta=-0.05,
            completed_at=datetime.now(),
        )

        assert "0.80" in report.impact_summary
        assert "0.75" in report.impact_summary
        assert "-0.05" in report.impact_summary

    def test_no_change_summary(self):
        """Test impact summary for no change."""
        report = ImpactReport(
            recommendation_id="rec-123",
            description="Minor formatting change",
            readiness_before=0.70,
            readiness_after=0.70,
            readiness_delta=0.0,
            completed_at=datetime.now(),
        )

        assert "0.70" in report.impact_summary


class TestFormatImpactMessage:
    """Tests for format_impact_message function."""

    def test_positive_impact_message(self):
        """Test message formatting for positive impact."""
        measurement = RecommendationImpactMeasurement(
            recommendation_id="rec-123",
            recommendation_type="add_metric",
            target_achievement_id="ach-1",
            execution_status=RecommendationExecutionStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            readiness_delta=ReadinessDelta(
                before_overall=0.62,
                after_overall=0.74,
                delta=0.12,
            ),
        )

        message = format_impact_message(measurement)
        assert "0.62" in message
        assert "0.74" in message
        assert "+0.12" in message

    def test_negative_impact_message(self):
        """Test message formatting for negative impact."""
        measurement = RecommendationImpactMeasurement(
            recommendation_id="rec-123",
            recommendation_type="remove_redundant",
            target_achievement_id=None,
            execution_status=RecommendationExecutionStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            readiness_delta=ReadinessDelta(
                before_overall=0.80,
                after_overall=0.70,
                delta=-0.10,
            ),
        )

        message = format_impact_message(measurement)
        assert "0.80" in message
        assert "0.70" in message
        assert "-0.10" in message

    def test_no_readiness_delta_message(self):
        """Test message when delta is not measured."""
        measurement = RecommendationImpactMeasurement(
            recommendation_id="rec-123",
            recommendation_type="add_metric",
            target_achievement_id="ach-1",
            execution_status=RecommendationExecutionStatus.PENDING,
            started_at=datetime.now(),
            readiness_delta=None,
        )

        message = format_impact_message(measurement)
        assert "Impact не измерен" in message


class TestUserImpactSummary:
    """Tests for user impact summary logic."""

    def test_empty_measurements(self):
        """Test summary with no measurements."""
        from app.services.review_action_loop import ReviewActionLoop, RecommendationExecutor

        # Mock services
        mock_executor = type('MockExecutor', (), {
            'get_all_impact_measurements': lambda self: [],
            'get_impact_measurement': lambda self, x: None,
        })()

        loop = ReviewActionLoop(
            executor=mock_executor,  # type: ignore
            artifact_registry=None,
        )

        import asyncio
        summary = asyncio.run(loop.get_user_impact_summary(uuid4()))

        assert summary["total_recommendations_completed"] == 0
        assert summary["total_readiness_improvement"] == 0.0
        assert summary["average_improvement_per_recommendation"] == 0.0

    def test_with_measurements(self):
        """Test summary with multiple measurements."""
        from app.services.review_action_loop import ReviewActionLoop, RecommendationExecutionStatus, ReadinessDelta

        measurements = [
            RecommendationImpactMeasurement(
                recommendation_id="rec-1",
                recommendation_type="add_metric",
                target_achievement_id="ach-1",
                execution_status=RecommendationExecutionStatus.COMPLETED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                readiness_delta=ReadinessDelta(
                    before_overall=0.60,
                    after_overall=0.70,
                    delta=0.10,
                ),
            ),
            RecommendationImpactMeasurement(
                recommendation_id="rec-2",
                recommendation_type="add_evidence",
                target_achievement_id="ach-2",
                execution_status=RecommendationExecutionStatus.COMPLETED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                readiness_delta=ReadinessDelta(
                    before_overall=0.70,
                    after_overall=0.80,
                    delta=0.10,
                ),
            ),
        ]

        mock_executor = type('MockExecutor', (), {
            'get_all_impact_measurements': lambda self: measurements,
            'get_impact_measurement': lambda self, x: next((m for m in measurements if m.recommendation_id == x), None),
        })()

        loop = ReviewActionLoop(
            executor=mock_executor,  # type: ignore
            artifact_registry=None,
        )

        import asyncio
        summary = asyncio.run(loop.get_user_impact_summary(uuid4()))

        assert summary["total_recommendations_completed"] == 2
        assert summary["total_readiness_improvement"] == 0.20
        assert summary["average_improvement_per_recommendation"] == 0.10
