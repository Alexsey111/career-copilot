from datetime import datetime

from app.domain.progress_models import ReadinessSnapshot
from app.services.progress_tracking_service import ProgressTrackingService


class TestProgressTrackingService:

    def test_compare_snapshots_detects_improvement_and_regression(self) -> None:
        before = ReadinessSnapshot(
            snapshot_id="before",
            overall_score=0.65,
            ats_score=0.88,
            evidence_score=0.52,
            interview_score=0.60,
            coverage_score=0.52,
            quality_score=0.70,
            created_at=datetime.utcnow(),
        )

        after = ReadinessSnapshot(
            snapshot_id="after",
            overall_score=0.71,
            ats_score=0.71,
            evidence_score=0.81,
            interview_score=0.62,
            coverage_score=0.81,
            quality_score=0.73,
            created_at=datetime.utcnow(),
        )

        service = ProgressTrackingService()
        result = service.compare_snapshots(before, after)

        assert result.previous_score == 0.65
        assert result.current_score == 0.71
        assert result.delta == 0.06
        assert "coverage" in result.improved_areas
        assert "evidence" in result.improved_areas
        assert "ats" in result.regressed_areas
        assert result.blocking_issues_resolved == []
        assert result.new_blocking_issues == []

    def test_detect_improvements_and_regressions_return_readable_messages(self) -> None:
        before = ReadinessSnapshot(
            snapshot_id="before",
            overall_score=0.75,
            ats_score=0.88,
            evidence_score=0.52,
            interview_score=0.62,
            coverage_score=0.52,
            quality_score=0.74,
            created_at=datetime.utcnow(),
        )

        after = ReadinessSnapshot(
            snapshot_id="after",
            overall_score=0.69,
            ats_score=0.71,
            evidence_score=0.81,
            interview_score=0.62,
            coverage_score=0.81,
            quality_score=0.72,
            created_at=datetime.utcnow(),
        )

        service = ProgressTrackingService()

        improvements = service.detect_improvements(before, after)
        regressions = service.detect_regressions(before, after)
        insights = service.generate_coaching_insights(service.compare_snapshots(before, after))

        assert "Coverage improved: 0.52 → 0.81" in improvements
        assert "Evidence quality improved: 0.52 → 0.81" in improvements
        assert "ATS score dropped: 0.88 → 0.71" in regressions
        assert "Added metrics improved evidence quality." in insights
        assert "Removing Kubernetes mention reduced ATS alignment." in insights
