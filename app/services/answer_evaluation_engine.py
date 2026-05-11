from __future__ import annotations

import re
from typing import Any

from app.domain.coverage_eval_models import CoverageCheckResult
from app.domain.constants import (
    GENERIC_PATTERNS,
    CheckSeverity,
)


SPECIFIC_ACTION_VERBS = [
    r"\bimplemented\b",
    r"\bdeveloped\b",
    r"\bdesigned\b",
    r"\barchitected\b",
    r"\bcreated\b",
    r"\bbuilt\b",
    r"\bengineered\b",
    r"\bdeployed\b",
    r"\bautomated\b",
    r"\boptimized\b",
]

METRIC_PATTERNS = [
    r"\d+%",
    r"\d+\s*(users|customers|requests|tickets)",
    r"\$\d+",
    r"\d+\.?\d*\s*(ms|s|min|hr)",
    r"\d+\.?\d*\s*(kb|mb|gb|tb)",
]


class AnswerEvaluationEngine:
    """Детерминированный движок оценки ответов на вопросы интервью."""

    def __init__(
        self,
        answer: str,
        expected_competency: str | None = None,
    ):
        self.answer = answer
        self.expected_competency = expected_competency
        self.checks: list[CoverageCheckResult] = []

    def evaluate(self) -> list[CoverageCheckResult]:
        """Выполняет все проверки ответа."""
        self.check_specificity()
        self.check_star_completeness()
        self.check_evidence_quality()
        self.check_generic_wording()

        return self.checks

    def check_specificity(self) -> None:
        """Проверяет конкретику ответа (action verbs + metrics)."""
        answer_lower = self.answer.lower()

        action_verbs_count = sum(
            1 for pattern in SPECIFIC_ACTION_VERBS
            if re.search(pattern, answer_lower)
        )

        metrics_count = sum(
            1 for pattern in METRIC_PATTERNS
            if re.search(pattern, answer_lower)
        )

        specificity_score = action_verbs_count + metrics_count

        if specificity_score >= 2:
            self.checks.append(CoverageCheckResult(
                passed=True,
                check_name="specificity",
                message=f"High specificity: {action_verbs_count} verbs, {metrics_count} metrics",
                severity=CheckSeverity.INFO,
            ))
        elif specificity_score == 1:
            self.checks.append(CoverageCheckResult(
                passed=True,
                check_name="specificity",
                message=f"Moderate specificity: {action_verbs_count} verbs, {metrics_count} metrics",
                severity=CheckSeverity.INFO,
            ))
        else:
            self.checks.append(CoverageCheckResult(
                passed=False,
                check_name="specificity",
                message="Low specificity: no concrete action verbs or metrics",
                severity=CheckSeverity.WARNING,
            ))

    def check_star_completeness(self) -> None:
        """Проверяет полноту STAR-компонентов в ответе."""
        answer_lower = self.answer.lower()

        situation_indicators = [r"\bsituation\b", r"\bcontext\b", r"\bwhen\b", r"\bwhile\b"]
        task_indicators = [r"\btask\b", r"\bgoal\b", r"\bobjective\b", r"\bneeded to\b"]
        result_indicators = [r"\bresult\b", r"\boutcome\b", r"\bleading to\b", r"\bincluding\b"]

        has_situation = any(re.search(p, answer_lower) for p in situation_indicators)
        has_task = any(re.search(p, answer_lower) for p in task_indicators)
        has_action = any(re.search(p, answer_lower) for p in SPECIFIC_ACTION_VERBS)
        has_result = any(re.search(p, answer_lower) for p in result_indicators)

        components_found = sum([has_situation, has_task, has_action, has_result])

        if components_found >= 3:
            self.checks.append(CoverageCheckResult(
                passed=True,
                check_name="star_completeness",
                message=f"STAR complete: {components_found}/4 components",
                severity=CheckSeverity.INFO,
            ))
        elif components_found >= 2:
            self.checks.append(CoverageCheckResult(
                passed=True,
                check_name="star_completeness",
                message=f"STAR partial: {components_found}/4 components",
                severity=CheckSeverity.INFO,
            ))
        else:
            self.checks.append(CoverageCheckResult(
                passed=False,
                check_name="star_completeness",
                message=f"STAR incomplete: only {components_found}/4 components",
                severity=CheckSeverity.WARNING,
            ))

    def check_evidence_quality(self) -> None:
        """Проверяет наличие измеримых доказательств."""
        answer_lower = self.answer.lower()

        metrics_found = any(
            re.search(pattern, answer_lower)
            for pattern in METRIC_PATTERNS
        )

        quantified_actions = bool(
            re.search(r"\b\d+\s*(times|projects|teams|people)", answer_lower)
        )

        if metrics_found or quantified_actions:
            self.checks.append(CoverageCheckResult(
                passed=True,
                check_name="evidence_quality",
                message="Evidence includes measurable outcomes",
                severity=CheckSeverity.INFO,
            ))
        else:
            self.checks.append(CoverageCheckResult(
                passed=False,
                check_name="evidence_quality",
                message="No measurable evidence provided",
                severity=CheckSeverity.WARNING,
            ))

    def check_generic_wording(self) -> None:
        """Проверяет на generic формулировки."""
        answer_lower = self.answer.lower()

        generic_found = [
            pattern for pattern in GENERIC_PATTERNS
            if re.search(pattern, answer_lower)
        ]

        if generic_found:
            self.checks.append(CoverageCheckResult(
                passed=False,
                check_name="generic_wording",
                message=f"Generic phrases detected: {', '.join(generic_found[:3])}",
                severity=CheckSeverity.WARNING,
            ))
        else:
            self.checks.append(CoverageCheckResult(
                passed=True,
                check_name="generic_wording",
                message="No generic wording detected",
                severity=CheckSeverity.INFO,
            ))

    @property
    def is_acceptable(self) -> bool:
        """Проверяет, проходит ли ответ минимальные требования."""
        return all(
            check.passed or check.severity != CheckSeverity.CRITICAL
            for check in self.checks
        )

    @property
    def overall_score(self) -> float:
        """Рассчитывает общий score ответа (0.0 - 1.0)."""
        if not self.checks:
            return 0.0

        passed_count = sum(1 for c in self.checks if c.passed)
        warning_count = sum(
            1 for c in self.checks
            if not c.passed and c.severity == CheckSeverity.WARNING
        )

        base_score = passed_count / len(self.checks)
        penalty = warning_count * 0.15

        return max(0.0, round(base_score - penalty, 2))
