from __future__ import annotations

from app.domain.coverage_models import RequirementCoverage
from app.domain.coverage_eval_models import CoverageEvaluationReport
from app.domain.readiness_models import ReadinessSignal
from app.domain.signals import UnifiedSignal


class SignalMigrationAdapters:
    """Adapters for migrating existing signals to UnifiedSignal format."""

    @staticmethod
    def from_coverage_requirements(
        coverage: list[RequirementCoverage],
        coverage_report: CoverageEvaluationReport | None = None,
    ) -> list[UnifiedSignal]:
        """Convert coverage requirements to unified signals."""
        signals: list[UnifiedSignal] = []

        # Overall coverage signal
        if coverage:
            supported = sum(1 for item in coverage if item.coverage_type != "unsupported")
            coverage_score = supported / len(coverage)

            # Use ATS match score if available
            if coverage_report and coverage_report.ats_match_score > 0:
                coverage_score = coverage_report.ats_match_score / 100.0

            signals.append(UnifiedSignal(
                signal_type="coverage",
                score=round(coverage_score, 3),
                weight=0.30,  # From COMPONENT_WEIGHTS
                source="coverage_mapping",
                metadata={
                    "total_requirements": len(coverage),
                    "supported_count": supported,
                    "ats_match_score": coverage_report.ats_match_score if coverage_report else None,
                },
            ))

        return signals

    @staticmethod
    def from_evidence_scores(evidence_scores: list[float]) -> list[UnifiedSignal]:
        """Convert evidence quality scores to unified signals."""
        if not evidence_scores:
            return []

        avg_score = sum(evidence_scores) / len(evidence_scores)

        return [UnifiedSignal(
            signal_type="evidence",
            score=round(avg_score, 3),
            weight=0.25,  # From COMPONENT_WEIGHTS
            source="evidence_quality",
            metadata={
                "individual_scores": evidence_scores,
                "score_count": len(evidence_scores),
            },
        )]

    @staticmethod
    def from_ats_score(ats_score: float | None) -> list[UnifiedSignal]:
        """Convert ATS preservation score to unified signals."""
        if ats_score is None or ats_score < 0:
            return []

        return [UnifiedSignal(
            signal_type="ats",
            score=round(ats_score, 3),
            weight=0.20,  # From COMPONENT_WEIGHTS
            source="ats_keyword_preservation",
            metadata={"ats_match_score": ats_score},
        )]

    @staticmethod
    def from_interview_score(interview_score: float | None) -> list[UnifiedSignal]:
        """Convert interview quality score to unified signals."""
        if interview_score is None or interview_score <= 0:
            return []

        return [UnifiedSignal(
            signal_type="interview",
            score=round(interview_score, 3),
            weight=0.15,  # From COMPONENT_WEIGHTS
            source="interview_answers",
            metadata={"quality_score": interview_score},
        )]

    @staticmethod
    def from_readiness_signals(readiness_signals: list[ReadinessSignal]) -> list[UnifiedSignal]:
        """Convert ReadinessSignal objects to UnifiedSignal."""
        return [
            UnifiedSignal(
                signal_type=signal.signal_type,
                score=signal.score,
                weight=signal.weight,
                source=signal.source,
                metadata=signal.metadata,
            )
            for signal in readiness_signals
        ]

    @staticmethod
    def create_quality_signal(
        coverage_signals: list[UnifiedSignal],
        evidence_signals: list[UnifiedSignal],
        ats_signals: list[UnifiedSignal],
        interview_signals: list[UnifiedSignal],
    ) -> UnifiedSignal:
        """Create composite quality signal from other signals."""
        all_signals = coverage_signals + evidence_signals + ats_signals + interview_signals

        if not all_signals:
            return UnifiedSignal(
                signal_type="quality",
                score=0.0,
                weight=0.10,  # From COMPONENT_WEIGHTS
                source="composite_quality",
                metadata={"reason": "no_signals_available"},
            )

        # Average of all available signal scores
        avg_score = sum(s.score for s in all_signals) / len(all_signals)

        return UnifiedSignal(
            signal_type="quality",
            score=round(avg_score, 3),
            weight=0.10,
            source="composite_quality",
            metadata={
                "component_signals": len(all_signals),
                "signal_types": list(set(s.signal_type for s in all_signals)),
            },
        )