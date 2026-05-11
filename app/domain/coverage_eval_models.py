# app\domain\coverage_eval_models.py

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.constants import CheckSeverity


@dataclass(slots=True)
class CoverageCheckResult:
    passed: bool
    check_name: str
    message: str
    severity: CheckSeverity | str = CheckSeverity.WARNING


@dataclass(slots=True)
class CoverageEvaluationReport:
    checks: list[CoverageCheckResult] = field(default_factory=list)
    ats_match_score: float = 0.0

    @property
    def is_safe(self) -> bool:
        return all(
            (check.severity != CheckSeverity.CRITICAL) or check.passed
            for check in self.checks
        )