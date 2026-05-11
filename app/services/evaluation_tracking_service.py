from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from app.domain.evaluation_models import EvaluationDiff, EvaluationSnapshot, SCHEMA_VERSION, SIGNAL_TAXONOMY_VERSION
from app.domain.normalized_signals import NormalizedSignal
from app.repositories.evaluation_repository import EvaluationRepository


class EvaluationTrackingService(Protocol):
    """Service for tracking evaluation history and trajectories."""

    @abstractmethod
    def create_snapshot(
        self,
        candidate_id: str,
        readiness_score: float,
        calibration_version: str,
        normalized_signals: list[NormalizedSignal],
        variance: float,
        confidence: float,
        recommendation_ids: list[str] | None = None,
        schema_version: str = SCHEMA_VERSION,
        signal_taxonomy_version: str = SIGNAL_TAXONOMY_VERSION,
    ) -> EvaluationSnapshot:
        """Create and persist a new evaluation snapshot."""
        ...

    @abstractmethod
    def get_trajectory(self, candidate_id: str, limit: int = 10) -> list[EvaluationSnapshot]:
        """Get evaluation trajectory for a candidate."""
        ...

    @abstractmethod
    def compare_evaluations(
        self,
        candidate_id: str,
        snapshot_a_id: str | None = None,
        snapshot_b_id: str | None = None,
    ) -> EvaluationDiff:
        """Compare two evaluations, defaulting to most recent vs previous."""
        ...


class DefaultEvaluationTrackingService:
    """Default implementation of evaluation tracking."""

    def __init__(self, repository: EvaluationRepository) -> None:
        self._repository = repository

    def create_snapshot(
        self,
        candidate_id: str,
        readiness_score: float,
        calibration_version: str,
        normalized_signals: list[NormalizedSignal],
        variance: float,
        confidence: float,
        recommendation_ids: list[str] | None = None,
        schema_version: str = SCHEMA_VERSION,
        signal_taxonomy_version: str = SIGNAL_TAXONOMY_VERSION,
    ) -> EvaluationSnapshot:
        """Create and persist a new evaluation snapshot."""
        snapshot_id = f"{candidate_id}_{datetime.now().timestamp()}"

        snapshot = EvaluationSnapshot(
            snapshot_id=snapshot_id,
            created_at=datetime.now(),
            readiness_score=round(readiness_score, 3),
            calibration_version=calibration_version,
            schema_version=schema_version,
            signal_taxonomy_version=signal_taxonomy_version,
            normalized_signals=normalized_signals,
            variance=round(variance, 6),
            confidence=round(confidence, 3),
            recommendation_ids=recommendation_ids or [],
        )

        self._repository.save_snapshot(snapshot)
        return snapshot

    def get_trajectory(self, candidate_id: str, limit: int = 10) -> list[EvaluationSnapshot]:
        """Get evaluation trajectory for a candidate."""
        return self._repository.get_snapshots_for_candidate(candidate_id, limit)

    def compare_evaluations(
        self,
        candidate_id: str,
        snapshot_a_id: str | None = None,
        snapshot_b_id: str | None = None,
    ) -> EvaluationDiff:
        """Compare two evaluations, defaulting to most recent vs previous."""
        trajectory = self.get_trajectory(candidate_id, limit=2)

        if len(trajectory) < 2:
            # Not enough snapshots to compare
            return EvaluationDiff(
                score_delta=0.0,
                confidence_delta=0.0,
                improved_signals=[],
                regressed_signals=[],
                newly_blocking=[],
            )

        # Use most recent as b, previous as a
        snapshot_b = trajectory[0]
        snapshot_a = trajectory[1]

        # Override if specific IDs provided
        if snapshot_a_id:
            snapshot_a = self._repository.get_snapshot(snapshot_a_id)
            if not snapshot_a:
                raise ValueError(f"Snapshot {snapshot_a_id} not found")
        if snapshot_b_id:
            snapshot_b = self._repository.get_snapshot(snapshot_b_id)
            if not snapshot_b:
                raise ValueError(f"Snapshot {snapshot_b_id} not found")

        return self._repository.compare_snapshots(snapshot_a, snapshot_b)