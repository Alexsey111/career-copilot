from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from app.domain.evaluation_models import EvaluationDiff, EvaluationSnapshot, SCHEMA_VERSION


class EvaluationRepository(Protocol):
    """Repository for persisting and retrieving evaluation snapshots."""

    @abstractmethod
    def save_snapshot(self, snapshot: EvaluationSnapshot) -> None:
        """Persist an evaluation snapshot."""
        ...

    @abstractmethod
    def get_snapshot(self, snapshot_id: str) -> EvaluationSnapshot | None:
        """Retrieve a snapshot by ID."""
        ...

    @abstractmethod
    def get_snapshots_for_candidate(self, candidate_id: str, limit: int = 10) -> list[EvaluationSnapshot]:
        """Get recent snapshots for a candidate."""
        ...

    @abstractmethod
    def compare_snapshots(self, snapshot_a: EvaluationSnapshot, snapshot_b: EvaluationSnapshot) -> EvaluationDiff:
        """Compare two snapshots and return the diff."""
        ...


class InMemoryEvaluationRepository:
    """In-memory implementation for testing/development."""

    def __init__(self) -> None:
        self._snapshots: dict[str, EvaluationSnapshot] = {}
        self._candidate_snapshots: dict[str, list[str]] = {}  # candidate_id -> [snapshot_ids]

    def save_snapshot(self, snapshot: EvaluationSnapshot) -> None:
        """Persist an evaluation snapshot."""
        self._snapshots[snapshot.snapshot_id] = snapshot

        # Extract candidate_id from snapshot_id (assuming format: candidate_id_timestamp)
        candidate_id = snapshot.snapshot_id.split('_')[0] if '_' in snapshot.snapshot_id else snapshot.snapshot_id
        if candidate_id not in self._candidate_snapshots:
            self._candidate_snapshots[candidate_id] = []
        self._candidate_snapshots[candidate_id].append(snapshot.snapshot_id)

    def get_snapshot(self, snapshot_id: str) -> EvaluationSnapshot | None:
        """Retrieve a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def get_snapshots_for_candidate(self, candidate_id: str, limit: int = 10) -> list[EvaluationSnapshot]:
        """Get recent snapshots for a candidate."""
        snapshot_ids = self._candidate_snapshots.get(candidate_id, [])
        snapshots = [self._snapshots[sid] for sid in snapshot_ids if sid in self._snapshots]
        # Sort by snapshot_id descending (assuming timestamp in id)
        snapshots.sort(key=lambda s: s.snapshot_id, reverse=True)
        return snapshots[:limit]

    def compare_snapshots(self, snapshot_a: EvaluationSnapshot, snapshot_b: EvaluationSnapshot) -> EvaluationDiff:
        """Compare two snapshots and return the diff."""
        score_delta = snapshot_b.readiness_score - snapshot_a.readiness_score
        confidence_delta = snapshot_b.confidence - snapshot_a.confidence

        # Compare signals
        improved_signals = []
        regressed_signals = []

        # Group signals by type
        signals_a = {s.type.value: s for s in snapshot_a.normalized_signals}
        signals_b = {s.type.value: s for s in snapshot_b.normalized_signals}

        for signal_type in set(signals_a.keys()) | set(signals_b.keys()):
            score_a = signals_a.get(signal_type, None)
            score_b = signals_b.get(signal_type, None)

            if score_a and score_b:
                if score_b.effective_score > score_a.effective_score:
                    improved_signals.append(signal_type)
                elif score_b.effective_score < score_a.effective_score:
                    regressed_signals.append(signal_type)
            elif score_b and not score_a:
                improved_signals.append(signal_type)  # New signal
            elif score_a and not score_b:
                regressed_signals.append(signal_type)  # Lost signal

        # For now, no blocking issues logic - would need domain knowledge
        newly_blocking = []

        return EvaluationDiff(
            score_delta=round(score_delta, 3),
            confidence_delta=round(confidence_delta, 3),
            schema_version=SCHEMA_VERSION,
            improved_signals=improved_signals,
            regressed_signals=regressed_signals,
            newly_blocking=newly_blocking,
        )