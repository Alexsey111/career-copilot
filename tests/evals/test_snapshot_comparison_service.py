from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.evaluation_snapshot import EvaluationSnapshot
from app.services.snapshot_comparison_service import SnapshotComparisonService


class FakeSnapshotRepository:
    def __init__(self, snapshots: list[EvaluationSnapshot]) -> None:
        self._snapshots = {snapshot.id: snapshot for snapshot in snapshots}

    async def get_by_id(self, session, snapshot_id):  # noqa: ANN001
        return self._snapshots.get(snapshot_id)


def build_snapshot(
    *,
    overall_score: float,
    ats_score: float,
    evidence_score: float,
    coverage_score: float,
    quality_score: float,
    blockers: list[str],
    warnings: list[str],
) -> EvaluationSnapshot:
    return EvaluationSnapshot(
        id=uuid4(),
        document_id=uuid4(),
        overall_score=overall_score,
        ats_score=ats_score,
        evidence_score=evidence_score,
        coverage_score=coverage_score,
        quality_score=quality_score,
        readiness_level="needs_work",
        scoring_version="1",
        prompt_version="1",
        extractor_version="1",
        model_name="test",
        blockers_json=blockers,
        warnings_json=warnings,
        metadata_json={},
    )


class TestSnapshotComparisonService:
    @pytest.mark.asyncio
    async def test_compare_snapshots(self) -> None:
        before = build_snapshot(
            overall_score=0.55,
            ats_score=0.60,
            evidence_score=0.45,
            coverage_score=0.50,
            quality_score=0.40,
            blockers=["missing_metrics", "weak_evidence"],
            warnings=["too_short"],
        )
        after = build_snapshot(
            overall_score=0.72,
            ats_score=0.78,
            evidence_score=0.61,
            coverage_score=0.69,
            quality_score=0.55,
            blockers=["weak_evidence", "new_blocker"],
            warnings=["too_short", "new_warning"],
        )
        after.document_id = before.document_id

        service = SnapshotComparisonService(FakeSnapshotRepository([before, after]))

        comparison = await service.compare_snapshots(
            session=None,
            before_snapshot_id=before.id,
            after_snapshot_id=after.id,
        )

        assert comparison.overall_delta == pytest.approx(0.17)
        assert comparison.ats_delta == pytest.approx(0.18)
        assert comparison.coverage_delta == pytest.approx(0.19)
        assert comparison.evidence_delta == pytest.approx(0.16)
        assert comparison.quality_delta == pytest.approx(0.15)
        assert comparison.resolved_blockers == ["missing_metrics"]
        assert comparison.new_blockers == ["new_blocker"]
        assert comparison.resolved_warnings == []
        assert comparison.new_warnings == ["new_warning"]

    @pytest.mark.asyncio
    async def test_compare_snapshots_missing_snapshot(self) -> None:
        snapshot = build_snapshot(
            overall_score=0.5,
            ats_score=0.5,
            evidence_score=0.5,
            coverage_score=0.5,
            quality_score=0.5,
            blockers=[],
            warnings=[],
        )
        service = SnapshotComparisonService(FakeSnapshotRepository([snapshot]))

        with pytest.raises(ValueError):
            await service.compare_snapshots(
                session=None,
                before_snapshot_id=uuid4(),
                after_snapshot_id=snapshot.id,
            )

    @pytest.mark.asyncio
    async def test_score_delta_exact_value(self) -> None:
        """Test exact score delta value of 0.12."""
        before = build_snapshot(
            overall_score=0.50,
            ats_score=0.60,
            evidence_score=0.45,
            coverage_score=0.50,
            quality_score=0.40,
            blockers=["weak_evidence"],
            warnings=["too_short"],
        )
        after = build_snapshot(
            overall_score=0.62,
            ats_score=0.70,
            evidence_score=0.55,
            coverage_score=0.60,
            quality_score=0.50,
            blockers=["weak_evidence"],
            warnings=["too_short", "new_warning"],
        )
        after.document_id = before.document_id

        service = SnapshotComparisonService(FakeSnapshotRepository([before, after]))

        comparison = await service.compare_snapshots(
            session=None,
            before_snapshot_id=before.id,
            after_snapshot_id=after.id,
        )

        assert comparison.overall_delta == 0.12

    @pytest.mark.asyncio
    async def test_blocker_resolution(self) -> None:
        """Test that missing_metrics blocker is resolved."""
        before = build_snapshot(
            overall_score=0.50,
            ats_score=0.60,
            evidence_score=0.45,
            coverage_score=0.50,
            quality_score=0.40,
            blockers=["missing_metrics", "weak_evidence"],
            warnings=["too_short"],
        )
        after = build_snapshot(
            overall_score=0.62,
            ats_score=0.70,
            evidence_score=0.55,
            coverage_score=0.60,
            quality_score=0.50,
            blockers=["weak_evidence"],
            warnings=["too_short"],
        )
        after.document_id = before.document_id

        service = SnapshotComparisonService(FakeSnapshotRepository([before, after]))

        comparison = await service.compare_snapshots(
            session=None,
            before_snapshot_id=before.id,
            after_snapshot_id=after.id,
        )

        assert "missing_metrics" in comparison.resolved_blockers
