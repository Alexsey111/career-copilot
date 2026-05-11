from datetime import datetime

from app.domain.evaluation_models import EvaluationDiff, EvaluationSnapshot
from app.domain.normalized_signals import NormalizedSignal, SignalTaxonomy, SignalType


class TestEvaluationSnapshot:

    def test_evaluation_snapshot_creation(self) -> None:
        signals = [
            NormalizedSignal(
                type=SignalType.COVERAGE,
                taxonomy=SignalTaxonomy.STRUCTURAL,
                value=0.8,
                confidence=0.9,
                calibrated=True,
            )
        ]

        snapshot = EvaluationSnapshot(
            snapshot_id="test_123",
            created_at=datetime.now(),
            readiness_score=0.75,
            calibration_version="v1.0",
            schema_version="v1.0",
            signal_taxonomy_version="v1.0",
            normalized_signals=signals,
            variance=0.01,
            confidence=0.85,
            recommendation_ids=["rec1", "rec2"],
        )

        assert snapshot.snapshot_id == "test_123"
        assert snapshot.readiness_score == 0.75
        assert snapshot.calibration_version == "v1.0"
        assert snapshot.schema_version == "v1.0"
        assert snapshot.signal_taxonomy_version == "v1.0"
        assert len(snapshot.normalized_signals) == 1
        assert snapshot.variance == 0.01
        assert snapshot.confidence == 0.85
        assert snapshot.recommendation_ids == ["rec1", "rec2"]


class TestEvaluationDiff:

    def test_evaluation_diff_creation(self) -> None:
        diff = EvaluationDiff(
            score_delta=0.1,
            confidence_delta=-0.05,
            schema_version="v1.0",
            improved_signals=["coverage", "evidence"],
            regressed_signals=["ats"],
            newly_blocking=["missing_experience"],
        )

        assert diff.score_delta == 0.1
        assert diff.confidence_delta == -0.05
        assert diff.schema_version == "v1.0"
        assert diff.improved_signals == ["coverage", "evidence"]
        assert diff.regressed_signals == ["ats"]
        assert diff.newly_blocking == ["missing_experience"]