from datetime import datetime
import time

from app.domain.evaluation_models import EvaluationSnapshot
from app.domain.normalized_signals import NormalizedSignal, SignalTaxonomy, SignalType
from app.repositories.evaluation_repository import InMemoryEvaluationRepository


class TestInMemoryEvaluationRepository:

    def test_save_and_get_snapshot(self) -> None:
        repo = InMemoryEvaluationRepository()

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
        )

        repo.save_snapshot(snapshot)

        retrieved = repo.get_snapshot("test_123")
        assert retrieved is not None
        assert retrieved.snapshot_id == "test_123"
        assert retrieved.readiness_score == 0.75

    def test_get_snapshots_for_candidate(self) -> None:
        repo = InMemoryEvaluationRepository()

        # Create multiple snapshots for same candidate
        for i in range(3):
            snapshot = EvaluationSnapshot(
                snapshot_id=f"candidate1_{i}",
                created_at=datetime.now(),
                readiness_score=0.7 + i * 0.1,
                calibration_version="v1.0",
                schema_version="v1.0",
                signal_taxonomy_version="v1.0",
                normalized_signals=[],
            )
            repo.save_snapshot(snapshot)
            time.sleep(0.01)  # Ensure different timestamps

        snapshots = repo.get_snapshots_for_candidate("candidate1", limit=2)
        assert len(snapshots) == 2
        # Should be sorted by snapshot_id descending (newest first)
        assert snapshots[0].snapshot_id > snapshots[1].snapshot_id

    def test_compare_snapshots(self) -> None:
        repo = InMemoryEvaluationRepository()

        signals_a = [
            NormalizedSignal(
                type=SignalType.COVERAGE,
                taxonomy=SignalTaxonomy.STRUCTURAL,
                value=0.7,
                confidence=0.8,
                calibrated=False,
            )
        ]

        signals_b = [
            NormalizedSignal(
                type=SignalType.COVERAGE,
                taxonomy=SignalTaxonomy.STRUCTURAL,
                value=0.8,
                confidence=0.9,
                calibrated=True,
            )
        ]

        snapshot_a = EvaluationSnapshot(
            snapshot_id="a",
            created_at=datetime.now(),
            readiness_score=0.7,
            calibration_version="v1.0",
            schema_version="v1.0",
            signal_taxonomy_version="v1.0",
            normalized_signals=signals_a,
            confidence=0.8,
        )

        snapshot_b = EvaluationSnapshot(
            snapshot_id="b",
            created_at=datetime.now(),
            readiness_score=0.8,
            calibration_version="v1.0",
            schema_version="v1.0",
            signal_taxonomy_version="v1.0",
            normalized_signals=signals_b,
            confidence=0.9,
        )

        diff = repo.compare_snapshots(snapshot_a, snapshot_b)

        assert diff.score_delta == 0.1
        assert diff.confidence_delta == 0.1
        assert diff.schema_version == "v1.0"
        assert "coverage" in diff.improved_signals