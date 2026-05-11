from app.services.coverage_evaluator import CoverageEvaluator
from app.domain.coverage_models import RequirementCoverage


class TestRequirementCoverageEvals:
    """Минимальный набор eval тестов для CoverageEvaluator."""

    def test_unsupported_requirement_critical(self) -> None:
        """unsupported requirement → critical → report.is_safe = False"""
        coverage = [
            RequirementCoverage(
                requirement_text="навыки управления командой",
                keyword="управление",
                coverage_type="unsupported",
                coverage_strength=0.0,
                evidence_strength="missing",
                priority="critical",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert not report.is_safe
        unsupported_check = next(
            c for c in report.checks if c.check_name == "no_unsupported_critical_requirements"
        )
        assert not unsupported_check.passed
        assert unsupported_check.severity == "critical"

    def test_direct_coverage_without_evidence_warning(self) -> None:
        """direct coverage без evidence → warning"""
        coverage = [
            RequirementCoverage(
                requirement_text="разработка ETL pipeline",
                keyword="ETL",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="weak",
                matched_achievement_ids=["ach-1"],
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert report.is_safe
        evidence_check = next(
            c for c in report.checks if c.check_name == "no_missing_evidence"
        )
        assert not evidence_check.passed
        assert evidence_check.severity == "warning"

    def test_direct_coverage_without_achievements_critical(self) -> None:
        """direct coverage без achievements → critical"""
        coverage = [
            RequirementCoverage(
                requirement_text="разработка ETL pipeline",
                keyword="ETL",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="missing",
                matched_achievement_ids=[],
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert not report.is_safe
        fake_check = next(
            c for c in report.checks if c.check_name == "no_fake_direct_coverage"
        )
        assert not fake_check.passed
        assert fake_check.severity == "critical"

    def test_empty_coverage_critical(self) -> None:
        """empty coverage → critical"""
        coverage: list[RequirementCoverage] = []

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert not report.is_safe
        empty_check = next(
            c for c in report.checks if c.check_name == "no_empty_coverage_mapping"
        )
        assert not empty_check.passed
        assert empty_check.severity == "critical"

    def test_valid_coverage_safe(self) -> None:
        """valid coverage → safe"""
        coverage = [
            RequirementCoverage(
                requirement_text="разработка ETL pipeline",
                keyword="ETL",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="strong",
                matched_achievement_ids=["ach-1"],
                evidence_summary="прототип в GitHub",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert report.is_safe
        for check in report.checks:
            if not check.passed:
                assert check.severity != "critical"

    def test_ats_match_score_calculation(self) -> None:
        """Проверка расчёта ATS Match Score."""
        coverage = [
            # critical matched
            RequirementCoverage(
                requirement_text="разработка ETL",
                keyword="ETL",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="strong",
                matched_achievement_ids=["ach-1"],
                priority="critical",
            ),
            # important matched
            RequirementCoverage(
                requirement_text="анализ данных",
                keyword="анализ",
                coverage_type="direct",
                coverage_strength=0.7,
                evidence_strength="strong",
                matched_achievement_ids=["ach-2"],
                priority="important",
            ),
            # optional unsupported
            RequirementCoverage(
                requirement_text="навыки презентации",
                keyword="презентация",
                coverage_type="unsupported",
                coverage_strength=0.0,
                evidence_strength="missing",
                priority="optional",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        # Формула: (1.0 + 0.7) / (1.0 + 0.7 + 0.3) = 1.7 / 2.0 = 85%
        assert report.ats_match_score == 85.0

    def test_score_inflation_warning(self) -> None:
        """Высокий coverage_strength без strong evidence → warning."""
        coverage = [
            RequirementCoverage(
                requirement_text="Python backend development",
                keyword="Python",
                coverage_type="partial",
                coverage_strength=0.75,  # высокий score
                evidence_strength="weak",  # но слабое evidence
                matched_achievement_ids=["ach-1"],
                priority="important",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert report.is_safe  # warning не делает unsafe
        inflation_check = next(
            c for c in report.checks if c.check_name == "no_score_inflation"
        )
        assert not inflation_check.passed
        assert inflation_check.severity == "warning"

    def test_score_inflation_missing_evidence(self) -> None:
        """Высокий coverage_strength с missing evidence → warning."""
        coverage = [
            RequirementCoverage(
                requirement_text="Java microservices",
                keyword="microservices",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="missing",
                matched_achievement_ids=["ach-1"],
                priority="critical",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert report.is_safe
        inflation_check = next(
            c for c in report.checks if c.check_name == "no_score_inflation"
        )
        assert not inflation_check.passed
        assert inflation_check.severity == "warning"

    def test_no_score_inflation_when_strong_evidence(self) -> None:
        """Высокий coverage_strength с strong evidence → pass."""
        coverage = [
            RequirementCoverage(
                requirement_text="Python backend development",
                keyword="Python",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="strong",
                matched_achievement_ids=["ach-1"],
                priority="important",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        inflation_check = next(
            c for c in report.checks if c.check_name == "no_score_inflation"
        )
        assert inflation_check.passed

    def test_no_generic_evidence_warning(self) -> None:
        """Generic achievement как evidence → warning."""
        coverage = [
            RequirementCoverage(
                requirement_text="Python backend development",
                keyword="Python",
                coverage_type="partial",
                coverage_strength=0.6,
                evidence_strength="strong",
                matched_achievement_ids=["generic-1"],  # generic ID
                priority="important",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        assert report.is_safe  # warning не делает unsafe
        generic_check = next(
            c for c in report.checks if c.check_name == "no_generic_evidence"
        )
        assert not generic_check.passed
        assert generic_check.severity == "warning"

    def test_no_generic_evidence_pass(self) -> None:
        """Конкретные achievements → pass."""
        coverage = [
            RequirementCoverage(
                requirement_text="Python backend development",
                keyword="Python",
                coverage_type="direct",
                coverage_strength=0.85,
                evidence_strength="strong",
                matched_achievement_ids=["ach-specific-1"],
                priority="important",
            ),
        ]

        evaluator = CoverageEvaluator(coverage)
        report = evaluator.evaluate()

        generic_check = next(
            c for c in report.checks if c.check_name == "no_generic_evidence"
        )
        assert generic_check.passed
