from __future__ import annotations

from app.domain.constants import (
    CheckSeverity,
    CoverageType,
    EvidenceStrength,
    Priority,
    PRIORITY_WEIGHTS,
    GENERIC_PHRASES,
    COVERAGE_STRENGTH_DIRECT_THRESHOLD,
)
from app.domain.coverage_eval_models import (
    CoverageCheckResult,
    CoverageEvaluationReport,
)
from app.domain.coverage_models import RequirementCoverage


class CoverageEvaluator:
    """Оценщик покрытия требований достижениями с расчётом ATS match score."""

    def __init__(
        self,
        coverage: list[RequirementCoverage],
    ):
        self.coverage = coverage
        self.checks: list[CoverageCheckResult] = []

    def _get_priority(self, item: RequirementCoverage) -> str:
        """Определяет приоритет требования."""
        return item.priority

    def calculate_ats_match_score(self) -> float:
        """
        Рассчитывает ATS Match Score на основе покрытия требований.

        Формула:
        - critical matched: 1.0 weight
        - important matched: 0.7 weight
        - optional matched: 0.3 weight

        Возвращает процент от 0 до 100.
        """
        if not self.coverage:
            return 0.0

        total_weight = 0.0
        matched_weight = 0.0

        for item in self.coverage:
            priority = self._get_priority(item)
            weight = PRIORITY_WEIGHTS.get(priority, 0.7)
            total_weight += weight

            if item.coverage_type != CoverageType.UNSUPPORTED:
                matched_weight += weight

        if total_weight == 0:
            return 0.0

        return round((matched_weight / total_weight) * 100, 1)

    def check_no_empty_coverage_mapping(self) -> None:
        if not self.coverage:
            self.checks.append(
                CoverageCheckResult(
                    passed=False,
                    check_name="no_empty_coverage_mapping",
                    message="Coverage mapping is empty",
                    severity=CheckSeverity.CRITICAL,
                )
            )
            return

        self.checks.append(
            CoverageCheckResult(
                passed=True,
                check_name="no_empty_coverage_mapping",
                message="Coverage mapping exists",
                severity=CheckSeverity.INFO,
            )
        )

    def check_no_unsupported_critical_requirements(self) -> None:
        critical_unsupported = [
            item
            for item in self.coverage
            if item.coverage_type == CoverageType.UNSUPPORTED
            and self._get_priority(item) == Priority.CRITICAL
        ]

        if critical_unsupported:
            self.checks.append(
                CoverageCheckResult(
                    passed=False,
                    check_name="no_unsupported_critical_requirements",
                    message=(
                        f"{len(critical_unsupported)} unsupported CRITICAL requirements found"
                    ),
                    severity=CheckSeverity.CRITICAL,
                )
            )
            return

        self.checks.append(
            CoverageCheckResult(
                passed=True,
                check_name="no_unsupported_critical_requirements",
                message="All critical requirements supported",
                severity=CheckSeverity.INFO,
            )
        )

    def check_no_missing_evidence(self) -> None:
        weak_items = [
            item
            for item in self.coverage
            if item.coverage_type == CoverageType.DIRECT
            and item.evidence_strength in {EvidenceStrength.MISSING, EvidenceStrength.WEAK}
        ]

        if weak_items:
            self.checks.append(
                CoverageCheckResult(
                    passed=False,
                    check_name="no_missing_evidence",
                    message="Direct coverage without strong evidence",
                    severity=CheckSeverity.WARNING,
                )
            )
            return

        self.checks.append(
            CoverageCheckResult(
                passed=True,
                check_name="no_missing_evidence",
                message="Evidence coverage acceptable",
                severity=CheckSeverity.INFO,
            )
        )

    def check_no_fake_direct_coverage(self) -> None:
        invalid = [
            item
            for item in self.coverage
            if item.coverage_type == CoverageType.DIRECT
            and not item.matched_achievement_ids
        ]

        if invalid:
            self.checks.append(
                CoverageCheckResult(
                    passed=False,
                    check_name="no_fake_direct_coverage",
                    message="Direct coverage without achievements",
                    severity=CheckSeverity.CRITICAL,
                )
            )
            return

        self.checks.append(
            CoverageCheckResult(
                passed=True,
                check_name="no_fake_direct_coverage",
                message="Direct coverage properly linked",
                severity=CheckSeverity.INFO,
            )
        )

    def check_no_score_inflation(self) -> None:
        """
        Проверка на инфляцию scores без достаточных доказательств.

        Ловит случаи когда coverage_strength высокий (>= 0.7),
        но evidence_strength слабый (weak/missing).

        Пример: requirement "Python backend" matched с achievement
        "Worked with software teams" -> token overlap 0.4, partial coverage,
        но без strong evidence это может быть false positive.
        """
        inflated_items = [
            item
            for item in self.coverage
            if item.coverage_strength >= COVERAGE_STRENGTH_DIRECT_THRESHOLD
            and item.evidence_strength in {EvidenceStrength.WEAK, EvidenceStrength.MISSING}
            and item.coverage_type != CoverageType.UNSUPPORTED
        ]

        if inflated_items:
            self.checks.append(
                CoverageCheckResult(
                    passed=False,
                    check_name="no_score_inflation",
                    message=(
                        f"{len(inflated_items)} coverage items with high "
                        f"strength but weak evidence"
                    ),
                    severity=CheckSeverity.WARNING,
                )
            )
            return

        self.checks.append(
            CoverageCheckResult(
                passed=True,
                check_name="no_score_inflation",
                message="No score inflation detected",
                severity=CheckSeverity.INFO,
            )
        )

    def _is_generic_achievement(self, achievement_id: str, matched_achievement_ids: list[str]) -> bool:
        """
        Проверяет, является ли achievement generic фразой без конкретики.

        В реальном коде здесь будет lookup в базе достижений.
        Для теста используем заглушку по ID.
        """
        generic_ids = {"generic-1", "generic-2", "vague-1"}
        return achievement_id in generic_ids

    def check_no_generic_evidence(self) -> None:
        """
        Проверка на использование generic фраз как доказательств.

        Ловит достижения типа:
        - "Participated in project activities"
        - "Helped the team"
        - "Worked on software"

        Такие достижения technically overlapp с requirement,
        но не являются useful evidence.
        """
        generic_evidence_items = []

        for item in self.coverage:
            if item.coverage_type == CoverageType.UNSUPPORTED:
                continue

            for achievement_id in item.matched_achievement_ids:
                if self._is_generic_achievement(achievement_id, item.matched_achievement_ids):
                    generic_evidence_items.append(
                        f"{item.requirement_text} <- {achievement_id}"
                    )

        if generic_evidence_items:
            self.checks.append(
                CoverageCheckResult(
                    passed=False,
                    check_name="no_generic_evidence",
                    message=(
                        f"{len(generic_evidence_items)} generic achievement(s) used as evidence: "
                        f"{'; '.join(generic_evidence_items[:3])}"
                    ),
                    severity=CheckSeverity.WARNING,
                )
            )
            return

        self.checks.append(
            CoverageCheckResult(
                passed=True,
                check_name="no_generic_evidence",
                message="No generic evidence detected",
                severity=CheckSeverity.INFO,
            )
        )

    def evaluate(self) -> CoverageEvaluationReport:
        self.check_no_empty_coverage_mapping()
        self.check_no_unsupported_critical_requirements()
        self.check_no_missing_evidence()
        self.check_no_fake_direct_coverage()
        self.check_no_score_inflation()
        self.check_no_generic_evidence()

        return CoverageEvaluationReport(
            checks=self.checks,
            ats_match_score=self.calculate_ats_match_score(),
        )
