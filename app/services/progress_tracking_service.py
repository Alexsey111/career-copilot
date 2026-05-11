from __future__ import annotations

from app.domain.progress_models import ReadinessDelta, ReadinessSnapshot


class ProgressTrackingService:
    """Service for comparing readiness snapshots and generating progress insights."""

    SCORE_FIELDS = (
        "ats",
        "evidence",
        "interview",
        "coverage",
        "quality",
    )

    AREA_LABELS = {
        "ats": "ATS score",
        "evidence": "Evidence quality",
        "interview": "Interview score",
        "coverage": "Coverage",
        "quality": "Quality",
    }

    IMPROVEMENT_MESSAGES = {
        "ats": "Refining keywords improved ATS alignment.",
        "evidence": "Added metrics improved evidence quality.",
        "interview": "Clarifying examples improved interview readiness.",
        "coverage": "Expanding coverage improved overall readiness.",
        "quality": "Improving wording raised overall quality.",
    }

    REGRESSION_MESSAGES = {
        "ats": "Removing Kubernetes mention reduced ATS alignment.",
        "evidence": "Simplifying evidence reduced evidence quality.",
        "interview": "Shortening examples weakened interview readiness.",
        "coverage": "Dropping coverage reduced overall readiness.",
        "quality": "Less polish lowered overall quality.",
    }

    SCORE_THRESHOLD = 0.03

    def compare_snapshots(
        self,
        before: ReadinessSnapshot,
        after: ReadinessSnapshot,
    ) -> ReadinessDelta:
        """Compares two readiness snapshots and returns the computed delta."""
        improved_areas: list[str] = []
        regressed_areas: list[str] = []

        for area in self.SCORE_FIELDS:
            before_score = getattr(before, f"{area}_score")
            after_score = getattr(after, f"{area}_score")

            if after_score > before_score + self.SCORE_THRESHOLD:
                improved_areas.append(area)
            elif after_score < before_score - self.SCORE_THRESHOLD:
                regressed_areas.append(area)

        return ReadinessDelta(
            previous_score=before.overall_score,
            current_score=after.overall_score,
            delta=round(after.overall_score - before.overall_score, 3),
            improved_areas=improved_areas,
            regressed_areas=regressed_areas,
            blocking_issues_resolved=[],
            new_blocking_issues=[],
        )

    def detect_improvements(
        self,
        before: ReadinessSnapshot,
        after: ReadinessSnapshot,
    ) -> list[str]:
        delta = self.compare_snapshots(before, after)
        return [
            self._format_change(area, before, after, improved=True)
            for area in delta.improved_areas
        ]

    def detect_regressions(
        self,
        before: ReadinessSnapshot,
        after: ReadinessSnapshot,
    ) -> list[str]:
        delta = self.compare_snapshots(before, after)
        return [
            self._format_change(area, before, after, improved=False)
            for area in delta.regressed_areas
        ]

    def generate_coaching_insights(
        self,
        delta: ReadinessDelta,
    ) -> list[str]:
        insights: list[str] = []

        for area in delta.improved_areas:
            insights.append(self.IMPROVEMENT_MESSAGES.get(
                area,
                f"{self.AREA_LABELS.get(area, area).capitalize()} improved.",
            ))

        for area in delta.regressed_areas:
            insights.append(self.REGRESSION_MESSAGES.get(
                area,
                f"{self.AREA_LABELS.get(area, area).capitalize()} dropped.",
            ))

        if not insights:
            insights.append("No coaching insights are available for this comparison.")

        return insights

    def track_progress(
        self,
        before: ReadinessSnapshot,
        after: ReadinessSnapshot,
    ) -> dict[str, object]:
        delta = self.compare_snapshots(before, after)
        return {
            "delta": delta,
            "improvements": self.detect_improvements(before, after),
            "regressions": self.detect_regressions(before, after),
            "insights": self.generate_coaching_insights(delta),
        }

    def _format_change(
        self,
        area: str,
        before: ReadinessSnapshot,
        after: ReadinessSnapshot,
        improved: bool,
    ) -> str:
        label = self.AREA_LABELS.get(area, area)
        before_score = getattr(before, f"{area}_score")
        after_score = getattr(after, f"{area}_score")
        verb = "improved" if improved else "dropped"
        return f"{label} {verb}: {before_score:.2f} → {after_score:.2f}"
