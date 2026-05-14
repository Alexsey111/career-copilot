from datetime import datetime, timedelta, timezone

from app.domain.analytics_models import TrajectoryClassification
from app.domain.evaluation_models import EvaluationSnapshot
from app.domain.normalized_signals import NormalizedSignal, SignalTaxonomy, SignalType
from app.repositories.evaluation_repository import InMemoryEvaluationRepository
from app.services.evaluation_analytics_service import DefaultEvaluationAnalyticsService


class TestDefaultEvaluationAnalyticsService:

    def test_analyze_trajectory_no_data(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationAnalyticsService(repo)

        trend = service.analyze_trajectory("candidate1")

        assert trend.candidate_id == "candidate1"
        assert trend.classification == TrajectoryClassification.STAGNATING
        assert trend.snapshot_count == 0
        assert trend.confidence == 0.0

    def test_analyze_trajectory_with_data(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationAnalyticsService(repo)

        # Create snapshots with improving trend
        base_time = datetime.now(timezone.utc)
        for i in range(5):
            snapshot = EvaluationSnapshot(
                snapshot_id=f"candidate1_{i}",
                created_at=base_time + timedelta(days=i),
                readiness_score=0.6 + i * 0.05,  # Improving: 0.6, 0.65, 0.7, 0.75, 0.8
                calibration_version="v1.0",
                schema_version="v1.0",
                signal_taxonomy_version="v1.0",
                normalized_signals=[],
                confidence=0.8 + i * 0.02,
            )
            repo.save_snapshot(snapshot)

        trend = service.analyze_trajectory("candidate1", days_back=30)

        assert trend.candidate_id == "candidate1"
        assert trend.snapshot_count == 5
        assert trend.average_score > 0.6
        assert trend.overall_trend_slope > 0  # Positive trend
        assert trend.classification in [TrajectoryClassification.IMPROVING, TrajectoryClassification.ACCELERATING]

    def test_analyze_signal_trends(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationAnalyticsService(repo)

        # Create snapshots with coverage signals
        base_time = datetime.now(timezone.utc)
        for i in range(3):
            signals = [
                NormalizedSignal(
                    type=SignalType.COVERAGE,
                    taxonomy=SignalTaxonomy.STRUCTURAL,
                    value=0.7 + i * 0.1,  # Improving: 0.7, 0.8, 0.9
                    confidence=0.8,
                    calibrated=False,
                )
            ]
            snapshot = EvaluationSnapshot(
                snapshot_id=f"candidate1_{i}",
                created_at=base_time + timedelta(days=i),
                readiness_score=0.7 + i * 0.05,
                calibration_version="v1.0",
                schema_version="v1.0",
                signal_taxonomy_version="v1.0",
                normalized_signals=signals,
            )
            repo.save_snapshot(snapshot)

        trends = service.analyze_signal_trends("candidate1", days_back=30)

        assert len(trends) == 1
        trend = trends[0]
        assert trend.signal_type == "coverage"
        assert trend.current_value == 0.9
        assert trend.average_value > 0.7
        assert trend.recent_change > 0

    def test_calculate_momentum(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationAnalyticsService(repo)

        # Create improving snapshots
        base_time = datetime.now(timezone.utc)
        for i in range(5):
            snapshot = EvaluationSnapshot(
                snapshot_id=f"candidate1_{i}",
                created_at=base_time + timedelta(days=i),
                readiness_score=0.6 + i * 0.05,
                calibration_version="v1.0",
                schema_version="v1.0",
                signal_taxonomy_version="v1.0",
                normalized_signals=[],
            )
            repo.save_snapshot(snapshot)

        momentum = service.calculate_momentum("candidate1")

        assert momentum.candidate_id == "candidate1"
        assert momentum.current_readiness == 0.8  # Latest score
        assert momentum.long_term_momentum > 0  # Positive momentum
        assert momentum.regression_risk < 0.5  # Low regression risk
        assert isinstance(momentum.trajectory_classification, TrajectoryClassification)
