from __future__ import annotations

from typing import Any

from app.config.scoring import COMPONENT_WEIGHTS
from app.domain.readiness_models import ReadinessSignal, ReadinessScore, RecommendationItem
from app.domain.coverage_models import RequirementCoverage
from app.domain.coverage_eval_models import CoverageEvaluationReport
from app.domain.constants import (
    EVIDENCE_SCORE_EXCELLENT_THRESHOLD,
    EVIDENCE_SCORE_GOOD_THRESHOLD,
    COVERAGE_STRENGTH_DIRECT_THRESHOLD,
)


# Веса компонентов для итоговой оценки
COMPONENT_WEIGHTS = {
    "coverage": 0.30,
    "evidence": 0.25,
    "ats": 0.20,
    "interview": 0.15,
    "quality": 0.10,
}


class ReadinessScoringService:
    """Сервис оценки готовности документа на основе всех источников."""

    def __init__(
        self,
        coverage: list[RequirementCoverage] | None = None,
        coverage_report: CoverageEvaluationReport | None = None,
        evidence_scores: list[float] | None = None,
        interview_quality_score: float | None = None,
        ats_preservation_score: float | None = None,
    ):
        self.coverage = coverage or []
        self.coverage_report = coverage_report
        self.evidence_scores = evidence_scores or []
        self.interview_quality_score = interview_quality_score
        self.ats_preservation_score = ats_preservation_score

    def calculate_readiness(self) -> ReadinessScore:
        """
        Рассчитывает итоговую оценку готовности документа.

        Собирает сигналы из:
        - coverage (покрытие требований)
        - evidence (качество доказательств)
        - ats (сохранение ключевых слов)
        - interview (качество ответов на вопросы)
        - quality (общее качество)
        """
        signals = self._collect_signals()
        component_scores = self._calculate_component_scores(signals)
        overall_score = self._calculate_overall_score(component_scores)
        blocking_issues = self._identify_blocking_issues(signals, component_scores)
        warnings = self._identify_warnings(signals, component_scores)
        recommendations = self._generate_recommendation(overall_score, blocking_issues, warnings)

        return ReadinessScore(
            overall_score=overall_score,
            ats_score=component_scores.get("ats", 0.0),
            evidence_score=component_scores.get("evidence", 0.0),
            interview_score=component_scores.get("interview", 0.0),
            coverage_score=component_scores.get("coverage", 0.0),
            quality_score=component_scores.get("quality", 0.0),
            blocking_issues=blocking_issues,
            warnings=warnings,
            recommendations=recommendations,
        )

    def _collect_signals(self) -> list[ReadinessSignal]:
        """Собирает сигналы из всех источников."""
        signals: list[ReadinessSignal] = []

        # Coverage signal
        coverage_score = self._calculate_coverage_score()
        signals.append(ReadinessSignal(
            signal_type="coverage",
            score=coverage_score,
            weight=COMPONENT_WEIGHTS["coverage"],
            source="coverage_mapping",
            metadata={"total_requirements": len(self.coverage)},
        ))

        # Evidence signal
        evidence_score = self._calculate_evidence_score()
        signals.append(ReadinessSignal(
            signal_type="evidence",
            score=evidence_score,
            weight=COMPONENT_WEIGHTS["evidence"],
            source="evidence_quality",
            metadata={"quality_scores": self.evidence_scores},
        ))

        # ATS signal
        ats_score = self.ats_preservation_score or self._estimate_ats_score()
        signals.append(ReadinessSignal(
            signal_type="ats",
            score=ats_score,
            weight=COMPONENT_WEIGHTS["ats"],
            source="ats_keyword_preservation",
            metadata={"ats_match_score": ats_score},
        ))

        # Interview signal
        interview_score = self.interview_quality_score or 0.0
        if interview_score > 0:
            signals.append(ReadinessSignal(
                signal_type="interview",
                score=interview_score,
                weight=COMPONENT_WEIGHTS["interview"],
                source="interview_answers",
                metadata={"quality_score": interview_score},
            ))

        # Quality signal (composite)
        quality_score = self._calculate_quality_score()
        signals.append(ReadinessSignal(
            signal_type="quality",
            score=quality_score,
            weight=COMPONENT_WEIGHTS["quality"],
            source="composite_quality_checks",
        ))

        return signals

    def _calculate_coverage_score(self) -> float:
        """Рассчитывает score покрытия требований."""
        if not self.coverage:
            return 0.0

        # Используем ats_match_score из coverage_report если доступен
        if self.coverage_report and self.coverage_report.ats_match_score > 0:
            return self.coverage_report.ats_match_score / 100.0

        # Иначе считаем вручную
        supported = sum(
            1 for item in self.coverage
            if item.coverage_type != "unsupported"
        )
        return round(supported / len(self.coverage), 3)

    def _calculate_evidence_score(self) -> float:
        """Рассчитывает score качества доказательств."""
        if not self.evidence_scores:
            return 0.0

        return sum(self.evidence_scores) / len(self.evidence_scores)

    def _estimate_ats_score(self) -> float:
        """Оценивает ATS score на основе покрытия."""
        if not self.coverage:
            return 0.0

        # Простая эвристика: процент требований с прямым покрытием
        direct = sum(
            1 for item in self.coverage
            if item.coverage_type == "direct"
        )
        return round(direct / len(self.coverage), 3)

    def _calculate_quality_score(self) -> float:
        """Рассчитывает общее качество."""
        # Усреднение всех доступных scores
        scores = [
            self._calculate_coverage_score(),
            self._calculate_evidence_score(),
            self.ats_preservation_score or 0.0,
            self.interview_quality_score or 0.0,
        ]

        valid_scores = [s for s in scores if s > 0]
        if not valid_scores:
            return 0.0

        return round(sum(valid_scores) / len(valid_scores), 3)

    def _calculate_component_scores(
        self,
        signals: list[ReadinessSignal],
    ) -> dict[str, float]:
        """Рассчитывает компонентные scores из сигналов."""
        return {
            signal.signal_type: signal.score
            for signal in signals
        }

    def _calculate_overall_score(
        self,
        component_scores: dict[str, float],
    ) -> float:
        """Рассчитывает итоговый score."""
        weighted_sum = 0.0
        total_weight = 0.0

        for component, weight in COMPONENT_WEIGHTS.items():
            score = component_scores.get(component, 0.0)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return round(weighted_sum, 3)

    def _identify_blocking_issues(
        self,
        signals: list[ReadinessSignal],
        component_scores: dict[str, float],
    ) -> list[str]:
        """Выявляет критические проблемы."""
        issues: list[str] = []

        # Coverage < 0.5
        if component_scores.get("coverage", 0) < 0.5:
            issues.append("Low coverage: less than 50% of requirements supported")

        # Evidence < 0.3
        if component_scores.get("evidence", 0) < 0.3:
            issues.append("Weak evidence: proof quality below acceptable threshold")

        # ATS < 0.6
        if component_scores.get("ats", 0) < 0.6:
            issues.append("Low ATS preservation: key skills may be lost")

        # Unsupported critical requirements
        if self.coverage_report:
            critical_checks = [
                c for c in self.coverage_report.checks
                if not c.passed and c.severity == "critical"
            ]
            if critical_checks:
                for check in critical_checks:
                    issues.append(f"Critical: {check.message}")

        # Empty coverage
        if not self.coverage:
            issues.append("No coverage mapping: requirements not linked to achievements")

        return issues

    def _identify_warnings(
        self,
        signals: list[ReadinessSignal],
        component_scores: dict[str, float],
    ) -> list[str]:
        """Выявляет предупреждения."""
        warnings: list[str] = []

        # Evidence moderate
        if 0.3 <= component_scores.get("evidence", 0) < EVIDENCE_SCORE_GOOD_THRESHOLD:
            warnings.append("Evidence quality is moderate - consider adding more specific metrics")

        # Interview low
        if component_scores.get("interview", 1.0) < 0.5:
            warnings.append("Interview answers need more specificity and STAR structure")

        # Coverage partial
        partial_count = sum(
            1 for item in self.coverage
            if item.coverage_type == "partial"
        )
        if partial_count > 0:
            warnings.append(f"{partial_count} requirements have only partial coverage")

        return warnings

    def _generate_recommendation(
        self,
        overall_score: float,
        blocking_issues: list[str],
        warnings: list[str],
    ) -> list[RecommendationItem]:
        """Генерирует рекомендации для документа."""
        recommendations: list[RecommendationItem] = []

        if overall_score >= 0.8 and not blocking_issues:
            recommendations.append(RecommendationItem(
                message="Document is ready for submission. High quality across all dimensions.",
                category="ready",
                severity="info",
            ))
            return recommendations

        if overall_score >= 0.6 and not blocking_issues:
            recommendations.append(RecommendationItem(
                message="Document is in good shape. Address warnings to improve quality.",
                category="quality",
                severity="info",
            ))
            return recommendations

        if overall_score >= 0.4:
            recommendations.append(RecommendationItem(
                message=(
                    "Document needs significant improvements. "
                    f"Priority: {'; '.join(blocking_issues[:2]) if blocking_issues else 'increase coverage and evidence quality'}."
                ),
                category="action",
                severity="warning",
            ))
            return recommendations

        recommendations.append(RecommendationItem(
            message=(
                "Document is not ready. Major work required on coverage, evidence, and ATS preservation."
            ),
            category="critical",
            severity="critical",
        ))
        return recommendations
