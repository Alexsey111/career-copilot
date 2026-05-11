from datetime import datetime

from app.domain.progress_models import ReadinessDelta, ReadinessSnapshot


class TestReadinessSnapshot:
    """Tests for the ReadinessSnapshot model."""

    def test_snapshot_fields_are_assigned(self) -> None:
        snapshot = ReadinessSnapshot(
            snapshot_id="snap-1",
            overall_score=0.72,
            ats_score=0.7,
            evidence_score=0.75,
            interview_score=0.65,
            coverage_score=0.8,
            quality_score=0.7,
            created_at=datetime.utcnow(),
        )

        assert snapshot.snapshot_id == "snap-1"
        assert snapshot.overall_score == 0.72
        assert snapshot.ats_score == 0.7
        assert snapshot.evidence_score == 0.75
        assert snapshot.interview_score == 0.65
        assert snapshot.coverage_score == 0.8
        assert snapshot.quality_score == 0.7
        assert snapshot.created_at is not None


class TestReadinessDelta:
    """Tests for the ReadinessDelta model."""

    def test_delta_fields_are_assigned(self) -> None:
        delta = ReadinessDelta(
            previous_score=0.5,
            current_score=0.7,
            delta=0.2,
            improved_areas=["ats"],
            regressed_areas=[],
            blocking_issues_resolved=[],
            new_blocking_issues=[],
        )

        assert delta.previous_score == 0.5
        assert delta.current_score == 0.7
        assert delta.delta == 0.2
        assert delta.improved_areas == ["ats"]
        assert delta.regressed_areas == []
        assert delta.blocking_issues_resolved == []
        assert delta.new_blocking_issues == []
