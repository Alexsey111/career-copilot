"""Snapshot comparison service for evaluation snapshot diffs."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_snapshot import EvaluationSnapshot
from app.repositories.evaluation_snapshot_repository import EvaluationSnapshotRepository


@dataclass(slots=True)
class SnapshotComparison:
    """Normalized comparison between two evaluation snapshots."""

    before_snapshot: EvaluationSnapshot
    after_snapshot: EvaluationSnapshot

    overall_delta: float
    ats_delta: float
    coverage_delta: float
    evidence_delta: float
    quality_delta: float

    blockers: list[str] = field(default_factory=list)
    resolved_blockers: list[str] = field(default_factory=list)
    new_blockers: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    resolved_warnings: list[str] = field(default_factory=list)
    new_warnings: list[str] = field(default_factory=list)


class SnapshotComparisonService:
    """Compare two evaluation snapshots and produce user-facing diffs."""

    def __init__(self, repository: EvaluationSnapshotRepository) -> None:
        self._repository = repository

    async def compare_snapshots(
        self,
        session: AsyncSession,
        before_snapshot_id: UUID,
        after_snapshot_id: UUID,
    ) -> SnapshotComparison:
        before_snapshot = await self._repository.get_by_id(session, before_snapshot_id)
        after_snapshot = await self._repository.get_by_id(session, after_snapshot_id)

        if before_snapshot is None:
            raise ValueError(f"before snapshot {before_snapshot_id} not found")
        if after_snapshot is None:
            raise ValueError(f"after snapshot {after_snapshot_id} not found")

        before_blockers = set(before_snapshot.blockers_json or [])
        after_blockers = set(after_snapshot.blockers_json or [])
        before_warnings = set(before_snapshot.warnings_json or [])
        after_warnings = set(after_snapshot.warnings_json or [])

        return SnapshotComparison(
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            overall_delta=after_snapshot.overall_score - before_snapshot.overall_score,
            ats_delta=after_snapshot.ats_score - before_snapshot.ats_score,
            coverage_delta=after_snapshot.coverage_score - before_snapshot.coverage_score,
            evidence_delta=after_snapshot.evidence_score - before_snapshot.evidence_score,
            quality_delta=after_snapshot.quality_score - before_snapshot.quality_score,
            blockers=sorted(before_blockers | after_blockers),
            resolved_blockers=sorted(before_blockers - after_blockers),
            new_blockers=sorted(after_blockers - before_blockers),
            warnings=sorted(before_warnings | after_warnings),
            resolved_warnings=sorted(before_warnings - after_warnings),
            new_warnings=sorted(after_warnings - before_warnings),
        )
