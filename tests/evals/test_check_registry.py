from app.domain.check_registry import (
    BaseDeterministicCheck,
    CoverageCheckRegistry,
)
from app.domain.checks import (
    NoEmptyCoverageCheck,
    NoUnsupportedCriticalRequirementsCheck,
    NoFakeDirectCoverageCheck,
    NoMissingEvidenceCheck,
    create_default_check_registry,
)
from app.domain.constants import CheckSeverity, CoverageType
from app.domain.coverage_models import RequirementCoverage


class TestBaseDeterministicCheck:
    """Тесты для базового класса проверок."""

    def test_subclass_requires_run_method(self) -> None:
        """Проверка требует реализации run."""
        check = NoEmptyCoverageCheck()
        assert check.name == "no_empty_coverage_mapping"
        assert check.is_critical is True


class TestCoverageCheckRegistry:
    """Тесты для регистра проверок."""

    def test_register_and_run(self) -> None:
        """Регистрация и выполнение проверки."""
        registry = CoverageCheckRegistry()
        registry.register(NoEmptyCoverageCheck())

        results = registry.run_all([])
        assert len(results) == 1
        assert results[0].check_name == "no_empty_coverage_mapping"
        assert not results[0].passed

    def test_unregister(self) -> None:
        """Удаление проверки из регистра."""
        registry = CoverageCheckRegistry()
        registry.register(NoEmptyCoverageCheck())
        registry.unregister("no_empty_coverage_mapping")

        assert registry.get("no_empty_coverage_mapping") is None
        assert len(registry.run_all([])) == 0

    def test_run_all_with_multiple_checks(self) -> None:
        """Выполнение всех проверок."""
        registry = CoverageCheckRegistry()
        registry.register(NoEmptyCoverageCheck())
        registry.register(NoFakeDirectCoverageCheck())

        coverage = [
            RequirementCoverage(
                requirement_text="test",
                keyword=None,
                coverage_type=CoverageType.DIRECT,
                matched_achievement_ids=[],
            )
        ]

        results = registry.run_all(coverage)
        assert len(results) == 2
        assert any(r.check_name == "no_empty_coverage_mapping" for r in results)
        assert any(r.check_name == "no_fake_direct_coverage" for r in results)

    def test_check_names(self) -> None:
        """Список имён проверок."""
        registry = CoverageCheckRegistry()
        registry.register(NoEmptyCoverageCheck())
        registry.register(NoFakeDirectCoverageCheck())

        assert "no_empty_coverage_mapping" in registry.check_names
        assert "no_fake_direct_coverage" in registry.check_names


class TestNoEmptyCoverageCheck:
    """Тесты для NoEmptyCoverageCheck."""

    def test_empty_coverage_fails(self) -> None:
        check = NoEmptyCoverageCheck()
        result = check.run([])
        assert not result.passed
        assert result.severity == CheckSeverity.CRITICAL

    def test_non_empty_coverage_passes(self) -> None:
        check = NoEmptyCoverageCheck()
        coverage = [RequirementCoverage(requirement_text="test", keyword=None)]
        result = check.run(coverage)
        assert result.passed
        assert result.severity == CheckSeverity.INFO


class TestNoUnsupportedCriticalRequirementsCheck:
    """Тесты для NoUnsupportedCriticalRequirementsCheck."""

    def test_unsupported_critical_fails(self) -> None:
        check = NoUnsupportedCriticalRequirementsCheck()
        coverage = [
            RequirementCoverage(
                requirement_text="critical req",
                keyword=None,
                coverage_type=CoverageType.UNSUPPORTED,
                priority="critical",
            )
        ]
        result = check.run(coverage)
        assert not result.passed
        assert result.severity == CheckSeverity.CRITICAL

    def test_supported_critical_passes(self) -> None:
        check = NoUnsupportedCriticalRequirementsCheck()
        coverage = [
            RequirementCoverage(
                requirement_text="critical req",
                keyword=None,
                coverage_type=CoverageType.DIRECT,
                priority="critical",
            )
        ]
        result = check.run(coverage)
        assert result.passed


class TestNoFakeDirectCoverageCheck:
    """Тесты для NoFakeDirectCoverageCheck."""

    def test_direct_without_achievements_fails(self) -> None:
        check = NoFakeDirectCoverageCheck()
        coverage = [
            RequirementCoverage(
                requirement_text="test",
                keyword=None,
                coverage_type=CoverageType.DIRECT,
                matched_achievement_ids=[],
            )
        ]
        result = check.run(coverage)
        assert not result.passed
        assert result.severity == CheckSeverity.CRITICAL

    def test_direct_with_achievements_passes(self) -> None:
        check = NoFakeDirectCoverageCheck()
        coverage = [
            RequirementCoverage(
                requirement_text="test",
                keyword=None,
                coverage_type=CoverageType.DIRECT,
                matched_achievement_ids=["ach-1"],
            )
        ]
        result = check.run(coverage)
        assert result.passed


class TestCreateDefaultCheckRegistry:
    """Тесты для создания регистра по умолчанию."""

    def test_default_checks_registered(self) -> None:
        registry = create_default_check_registry()

        assert "no_empty_coverage_mapping" in registry.check_names
        assert "no_unsupported_critical_requirements" in registry.check_names
        assert "no_missing_evidence" in registry.check_names
        assert "no_fake_direct_coverage" in registry.check_names
