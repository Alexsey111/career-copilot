from app.domain.readiness_models import RecommendationItem, ReadinessScore, ReadinessSignal
from app.domain.coverage_models import RequirementCoverage
from app.domain.coverage_eval_models import CoverageEvaluationReport, CoverageCheckResult
from app.domain.constants import CoverageType, CheckSeverity
from app.services.readiness_scoring_service import ReadinessScoringService


class TestReadinessScore:
    """Тесты для ReadinessScore модели."""

    def test_is_ready_when_no_blocking_and_high_score(self) -> None:
        score = ReadinessScore(
            overall_score=0.85,
            blocking_issues=[],
            warnings=["minor warning"],
            recommendations=[RecommendationItem(message="Ready")],
        )
        assert score.is_ready is True
        assert score.readiness_level == "ready"

    def test_not_ready_with_blocking_issues(self) -> None:
        score = ReadinessScore(
            overall_score=0.9,
            blocking_issues=["Critical issue"],
            warnings=[],
            recommendations=[RecommendationItem(message="Fix issues")],
        )
        assert score.is_ready is False
        # readiness_level зависит от score, а не от blocking_issues
        assert score.readiness_level in {"needs_work", "not_ready"}

    def test_needs_work_when_medium_score(self) -> None:
        score = ReadinessScore(
            overall_score=0.55,
            blocking_issues=[],
            warnings=[],
            recommendations=[RecommendationItem(message="Improve")],
        )
        assert score.is_ready is False
        assert score.readiness_level == "needs_work"


class TestReadinessScoringService:
    """Тесты для ReadinessScoringService."""

    def test_calculate_readiness_empty_coverage(self) -> None:
        service = ReadinessScoringService(coverage=[])
        result = service.calculate_readiness()

        assert result.overall_score == 0.0
        assert result.is_ready is False
        assert any("No coverage mapping" in issue for issue in result.blocking_issues)

    def test_calculate_readiness_good_coverage(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="Python development",
                keyword="Python",
                coverage_type=CoverageType.DIRECT,
                coverage_strength=0.85,
                evidence_strength="strong",
                matched_achievement_ids=["ach-1"],
                priority="important",
            ),
            RequirementCoverage(
                requirement_text="API design",
                keyword="API",
                coverage_type=CoverageType.DIRECT,
                coverage_strength=0.8,
                evidence_strength="strong",
                matched_achievement_ids=["ach-2"],
                priority="important",
            ),
        ]

        service = ReadinessScoringService(
            coverage=coverage,
            evidence_scores=[0.85, 0.8],
            ats_preservation_score=0.85,
            interview_quality_score=0.75,
        )

        result = service.calculate_readiness()

        assert result.coverage_score > 0.7
        assert result.evidence_score > 0.7
        assert result.overall_score > 0.6
        assert result.is_ready is True or result.readiness_level == "needs_work"

    def test_calculate_readiness_with_critical_issues(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="Critical requirement",
                keyword="critical",
                coverage_type=CoverageType.UNSUPPORTED,
                priority="critical",
            ),
        ]

        report = CoverageEvaluationReport(
            checks=[
                CoverageCheckResult(
                    passed=False,
                    check_name="no_unsupported_critical_requirements",
                    message="1 unsupported CRITICAL requirements found",
                    severity=CheckSeverity.CRITICAL,
                ),
            ],
            ats_match_score=30.0,
        )

        service = ReadinessScoringService(
            coverage=coverage,
            coverage_report=report,
        )

        result = service.calculate_readiness()

        assert result.is_ready is False
        assert any("Critical" in issue for issue in result.blocking_issues)

    def test_calculate_readiness_with_warnings(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="Test requirement",
                keyword=None,
                coverage_type=CoverageType.PARTIAL,
                coverage_strength=0.4,
                evidence_strength="moderate",
                matched_achievement_ids=["ach-1"],
            ),
        ]

        service = ReadinessScoringService(
            coverage=coverage,
            evidence_scores=[0.4],
        )

        result = service.calculate_readiness()

        assert any("partial coverage" in w.lower() for w in result.warnings)

    def test_calculate_coverage_score_direct(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="req1",
                keyword=None,
                coverage_type=CoverageType.DIRECT,
            ),
            RequirementCoverage(
                requirement_text="req2",
                keyword=None,
                coverage_type=CoverageType.DIRECT,
            ),
        ]

        service = ReadinessScoringService(coverage=coverage)
        score = service._calculate_coverage_score()

        assert score == 1.0

    def test_calculate_coverage_score_partial(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="req1",
                keyword=None,
                coverage_type=CoverageType.PARTIAL,
            ),
            RequirementCoverage(
                requirement_text="req2",
                keyword=None,
                coverage_type=CoverageType.UNSUPPORTED,
            ),
        ]

        service = ReadinessScoringService(coverage=coverage)
        score = service._calculate_coverage_score()

        assert score == 0.5

    def test_recommendation_ready(self) -> None:
        service = ReadinessScoringService(
            coverage=[
                RequirementCoverage(
                    requirement_text="test",
                    keyword=None,
                    coverage_type=CoverageType.DIRECT,
                ),
            ],
            evidence_scores=[0.8],
            ats_preservation_score=0.85,
        )

        result = service.calculate_readiness()

        assert result.overall_score >= 0.7
        assert result.recommendations
        assert "good" in result.recommendations[0].message.lower()

    def test_excellent_profile_scores_above_threshold(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="excellent profile",
                keyword="excellent",
                coverage_type=CoverageType.DIRECT,
                coverage_strength=0.95,
                evidence_strength="strong",
                matched_achievement_ids=["ach-1"],
                priority="important",
            ),
        ]

        service = ReadinessScoringService(
            coverage=coverage,
            evidence_scores=[0.95, 0.9],
            ats_preservation_score=0.9,
            interview_quality_score=0.9,
        )

        result = service.calculate_readiness()

        assert result.overall_score > 0.85
        assert result.recommendations
        assert result.recommendations[0].severity == "info"

    def test_recommendation_needs_work(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="test",
                keyword=None,
                coverage_type=CoverageType.PARTIAL,
                priority="important",
            ),
        ]

        service = ReadinessScoringService(
            coverage=coverage,
            evidence_scores=[0.3],
            ats_preservation_score=0.5,
        )

        result = service.calculate_readiness()

        assert result.overall_score < 0.8
        assert result.readiness_level in {"needs_work", "not_ready"}
