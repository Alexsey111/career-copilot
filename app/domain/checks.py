from __future__ import annotations

from app.domain.check_registry import BaseDeterministicCheck, CoverageCheckRegistry
from app.domain.constants import CheckSeverity, CoverageType
from app.domain.coverage_eval_models import CoverageCheckResult
from app.domain.coverage_models import RequirementCoverage


class NoEmptyCoverageCheck(BaseDeterministicCheck):
    """Проверка на пустое покрытие."""

    name = "no_empty_coverage_mapping"
    severity = "critical"

    def run(self, coverage: list[RequirementCoverage]) -> CoverageCheckResult:
        if not coverage:
            return CoverageCheckResult(
                passed=False,
                check_name=self.name,
                message="Coverage mapping is empty",
                severity=CheckSeverity.CRITICAL,
            )
        return CoverageCheckResult(
            passed=True,
            check_name=self.name,
            message="Coverage mapping exists",
            severity=CheckSeverity.INFO,
        )


class NoUnsupportedCriticalRequirementsCheck(BaseDeterministicCheck):
    """Проверка на unsupported critical требования."""

    name = "no_unsupported_critical_requirements"
    severity = "critical"

    def run(self, coverage: list[RequirementCoverage]) -> CoverageCheckResult:
        critical_unsupported = [
            item for item in coverage
            if item.coverage_type == CoverageType.UNSUPPORTED
            and item.priority == "critical"
        ]

        if critical_unsupported:
            return CoverageCheckResult(
                passed=False,
                check_name=self.name,
                message=f"{len(critical_unsupported)} unsupported CRITICAL requirements found",
                severity=CheckSeverity.CRITICAL,
            )
        return CoverageCheckResult(
            passed=True,
            check_name=self.name,
            message="All critical requirements supported",
            severity=CheckSeverity.INFO,
        )


class NoFakeDirectCoverageCheck(BaseDeterministicCheck):
    """Проверка на direct coverage без achievements."""

    name = "no_fake_direct_coverage"
    severity = "critical"

    def run(self, coverage: list[RequirementCoverage]) -> CoverageCheckResult:
        invalid = [
            item for item in coverage
            if item.coverage_type == CoverageType.DIRECT
            and not item.matched_achievement_ids
        ]

        if invalid:
            return CoverageCheckResult(
                passed=False,
                check_name=self.name,
                message="Direct coverage without achievements",
                severity=CheckSeverity.CRITICAL,
            )
        return CoverageCheckResult(
            passed=True,
            check_name=self.name,
            message="Direct coverage properly linked",
            severity=CheckSeverity.INFO,
        )


class NoMissingEvidenceCheck(BaseDeterministicCheck):
    """Проверка на direct coverage без strong evidence."""

    name = "no_missing_evidence"
    severity = "warning"

    def run(self, coverage: list[RequirementCoverage]) -> CoverageCheckResult:
        weak_items = [
            item for item in coverage
            if item.coverage_type == CoverageType.DIRECT
            and item.evidence_strength in {"missing", "weak"}
        ]

        if weak_items:
            return CoverageCheckResult(
                passed=False,
                check_name=self.name,
                message="Direct coverage without strong evidence",
                severity=CheckSeverity.WARNING,
            )
        return CoverageCheckResult(
            passed=True,
            check_name=self.name,
            message="Evidence coverage acceptable",
            severity=CheckSeverity.INFO,
        )


def create_default_check_registry() -> CoverageCheckRegistry:
    """Создаёт регистр с проверками по умолчанию."""

    registry = CoverageCheckRegistry()
    registry.register(NoEmptyCoverageCheck())
    registry.register(NoUnsupportedCriticalRequirementsCheck())
    registry.register(NoMissingEvidenceCheck())
    registry.register(NoFakeDirectCoverageCheck())
    return registry
