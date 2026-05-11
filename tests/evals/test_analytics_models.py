from datetime import datetime

from app.domain.analytics_models import (
    CandidateMomentum,
    RecommendationOutcome,
    SignalStability,
    SignalTrend,
    TrajectoryClassification,
    TrajectoryTrend,
)


class TestTrajectoryTrend:

    def test_trajectory_trend_creation(self) -> None:
        trend = TrajectoryTrend(
            candidate_id="candidate1",
            classification=TrajectoryClassification.IMPROVING,
            confidence=0.85,
            trend_strength=0.7,
            analysis_period_days=30,
            snapshot_count=10,
            average_score=0.75,
            score_volatility=0.05,
            recent_momentum=0.02,
            overall_trend_slope=0.003,
            stability_score=0.9,
            confidence_trend=0.01,
            analyzed_at=datetime.now(),
        )

        assert trend.candidate_id == "candidate1"
        assert trend.classification == TrajectoryClassification.IMPROVING
        assert trend.confidence == 0.85
        assert trend.trend_strength == 0.7
        assert trend.analysis_period_days == 30
        assert trend.snapshot_count == 10


class TestSignalTrend:

    def test_signal_trend_creation(self) -> None:
        trend = SignalTrend(
            signal_type="coverage",
            stability=SignalStability.IMPROVING,
            persistence_days=25,
            snapshot_count=8,
            current_value=0.8,
            average_value=0.7,
            value_volatility=0.1,
            recent_change=0.15,
            confidence_average=0.85,
            confidence_volatility=0.05,
            is_persistent_weakness=False,
            weakness_duration_days=0,
            weakness_threshold=0.6,
        )

        assert trend.signal_type == "coverage"
        assert trend.stability == SignalStability.IMPROVING
        assert trend.persistence_days == 25
        assert trend.is_persistent_weakness is False


class TestRecommendationOutcome:

    def test_recommendation_outcome_creation(self) -> None:
        outcome = RecommendationOutcome(
            recommendation_id="rec1",
            candidate_id="candidate1",
            issued_at=datetime.now(),
            recommendation_type="improve_coverage",
            target_signals=["coverage"],
            readiness_delta=0.1,
            signal_improvements={"coverage": 0.15},
            time_to_impact_days=7,
            effectiveness_score=0.8,
            was_followed=True,
            attributable_readiness_change=0.08,
        )

        assert outcome.recommendation_id == "rec1"
        assert outcome.effectiveness_score == 0.8
        assert outcome.attributable_readiness_change == 0.08


class TestCandidateMomentum:

    def test_candidate_momentum_creation(self) -> None:
        momentum = CandidateMomentum(
            candidate_id="candidate1",
            current_readiness=0.75,
            trajectory_classification=TrajectoryClassification.IMPROVING,
            short_term_momentum=0.02,
            medium_term_momentum=0.015,
            long_term_momentum=0.01,
            regression_risk=0.1,
            stagnation_risk=0.2,
            volatility_risk=0.05,
            critical_weaknesses=["interview"],
            recent_improvements=["coverage"],
            recommended_focus_areas=["interview"],
            analyzed_at=datetime.now(),
        )

        assert momentum.candidate_id == "candidate1"
        assert momentum.current_readiness == 0.75
        assert momentum.trajectory_classification == TrajectoryClassification.IMPROVING
        assert momentum.regression_risk == 0.1
        assert momentum.critical_weaknesses == ["interview"]