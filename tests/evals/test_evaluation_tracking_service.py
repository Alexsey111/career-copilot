from datetime import datetime
import time

from app.domain.evaluation_models import EvaluationSnapshot
from app.domain.normalized_signals import NormalizedSignal, SignalTaxonomy, SignalType
from app.repositories.evaluation_repository import InMemoryEvaluationRepository
from app.services.evaluation_tracking_service import DefaultEvaluationTrackingService


class TestDefaultEvaluationTrackingService:

    def test_create_snapshot(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationTrackingService(repo)

        signals = [
            NormalizedSignal(
                type=SignalType.COVERAGE,
                taxonomy=SignalTaxonomy.STRUCTURAL,
                value=0.8,
                confidence=0.9,
                calibrated=True,
            )
        ]

        snapshot = service.create_snapshot(
            candidate_id="candidate1",
            readiness_score=0.75,
            calibration_version="v1.0",
            normalized_signals=signals,
            variance=0.01,
            confidence=0.85,
            recommendation_ids=["rec1"],
        )

        assert snapshot.snapshot_id.startswith("candidate1_")
        assert snapshot.readiness_score == 0.75
        assert snapshot.calibration_version == "v1.0"
        assert snapshot.schema_version == "v1.0"
        assert snapshot.signal_taxonomy_version == "v1.0"
        assert len(snapshot.normalized_signals) == 1
        assert snapshot.recommendation_ids == ["rec1"]

        # Verify persisted
        retrieved = repo.get_snapshot(snapshot.snapshot_id)
        assert retrieved is not None
        assert retrieved.readiness_score == 0.75

    def test_get_trajectory(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationTrackingService(repo)

        # Create multiple snapshots
        for i in range(3):
            service.create_snapshot(
                candidate_id="candidate1",
                readiness_score=0.7 + i * 0.05,
                calibration_version="v1.0",
                normalized_signals=[],
                variance=0.0,
                confidence=0.8,
            )

        trajectory = service.get_trajectory("candidate1", limit=2)
        assert len(trajectory) == 2
        assert trajectory[0].readiness_score >= trajectory[1].readiness_score

    def test_compare_evaluations(self) -> None:
        repo = InMemoryEvaluationRepository()
        service = DefaultEvaluationTrackingService(repo)

        # Create two snapshots
        snapshot1 = service.create_snapshot(
            candidate_id="candidate1",
            readiness_score=0.7,
            calibration_version="v1.0",
            normalized_signals=[
                NormalizedSignal(
                    type=SignalType.COVERAGE,
                    taxonomy=SignalTaxonomy.STRUCTURAL,
                    value=0.7,
                    confidence=0.8,
                    calibrated=False,
                )
            ],
            variance=0.0,
            confidence=0.8,
        )

        time.sleep(0.01)  # Ensure different timestamps

        snapshot2 = service.create_snapshot(
            candidate_id="candidate1",
            readiness_score=0.8,
            calibration_version="v1.0",
            normalized_signals=[
                NormalizedSignal(
                    type=SignalType.COVERAGE,
                    taxonomy=SignalTaxonomy.STRUCTURAL,
                    value=0.8,
                    confidence=0.9,
                    calibrated=True,
                )
            ],
            variance=0.0,
            confidence=0.9,
        )

        diff = service.compare_evaluations("candidate1")

        assert diff.score_delta == 0.1
        assert diff.confidence_delta == 0.1
        assert diff.schema_version == "v1.0"
        assert "coverage" in diff.improved_signals