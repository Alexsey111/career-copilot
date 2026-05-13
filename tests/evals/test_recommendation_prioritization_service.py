from app.domain.readiness_models import RecommendationItem, RecommendationCategory
from app.services.recommendation_prioritization_service import RecommendationPrioritizationService


class TestRecommendationPrioritizationService:

    def test_prioritize_critical_blocker_highest(self) -> None:
        """Critical blocking issues should rank highest."""
        recommendations = [
            RecommendationItem(
                message="Document is in good shape. Address warnings to improve quality.",
                category=RecommendationCategory.STRUCTURE_IMPROVEMENT,
                severity="info",
            ),
            RecommendationItem(
                message="Document is not ready. Major work required on coverage, evidence, and ATS preservation.",
                category=RecommendationCategory.LOW_COVERAGE,
                severity="critical",
            ),
            RecommendationItem(
                message="Document needs significant improvements. Priority: increase coverage and evidence quality.",
                category=RecommendationCategory.WEAK_EVIDENCE,
                severity="warning",
            ),
        ]

        service = RecommendationPrioritizationService()
        prioritized = service.prioritize_recommendations(recommendations)

        # Critical should be first
        assert prioritized[0].recommendation.category == RecommendationCategory.LOW_COVERAGE
        assert prioritized[0].urgency == "high"
        assert prioritized[0].priority_score > prioritized[1].priority_score

    def test_effort_vs_impact_prioritization(self) -> None:
        """High impact with low effort should rank above low impact with high effort."""
        recommendations = [
            RecommendationItem(
                message="Replace generic evidence wording",
                category=RecommendationCategory.STRUCTURE_IMPROVEMENT,
                severity="info",
            ),
            RecommendationItem(
                message="Add measurable Kubernetes production impact",
                category=RecommendationCategory.MISSING_METRIC,
                severity="warning",
            ),
        ]

        service = RecommendationPrioritizationService()
        prioritized = service.prioritize_recommendations(recommendations)

        # High impact action should rank above low effort quality improvement
        assert prioritized[0].recommendation.message == "Add measurable Kubernetes production impact"
        assert prioritized[0].effort == "medium"
        assert prioritized[1].effort == "low"

    def test_get_top_recommendations_limits_results(self) -> None:
        """get_top_recommendations should return limited results."""
        recommendations = [
            RecommendationItem(message=f"Rec {i}", category=RecommendationCategory.STRUCTURE_IMPROVEMENT, severity="info")
            for i in range(5)
        ]

        service = RecommendationPrioritizationService()
        top = service.get_top_recommendations(recommendations, limit=3)

        assert len(top) == 3

    def test_impact_analysis_for_different_categories(self) -> None:
        """Different recommendation categories should have different impact estimates."""
        critical_rec = RecommendationItem(
            message="Critical issue",
            category=RecommendationCategory.LOW_COVERAGE,
            severity="critical",
        )
        quality_rec = RecommendationItem(
            message="Quality improvement",
            category=RecommendationCategory.STRUCTURE_IMPROVEMENT,
            severity="info",
        )

        service = RecommendationPrioritizationService()

        critical_impact = service._analyze_impact(critical_rec)
        quality_impact = service._analyze_impact(quality_rec)

        # LOW_COVERAGE with critical severity should have higher impact
        assert critical_impact.score_delta_estimate > quality_impact.score_delta_estimate
        assert critical_impact.confidence >= quality_impact.confidence
        assert len(critical_impact.affected_components) >= len(quality_impact.affected_components)

    def test_urgency_determination(self) -> None:
        """Urgency should be determined correctly based on severity and content."""
        critical_rec = RecommendationItem(
            message="Critical blocking issue",
            category=RecommendationCategory.LOW_COVERAGE,
            severity="critical",
        )
        warning_rec = RecommendationItem(
            message="Warning about quality",
            category=RecommendationCategory.WEAK_EVIDENCE,
            severity="warning",
        )
        info_rec = RecommendationItem(
            message="Info about readiness",
            category=RecommendationCategory.GENERAL,
            severity="info",
        )

        service = RecommendationPrioritizationService()

        assert service._determine_urgency(critical_rec) == "high"
        assert service._determine_urgency(warning_rec) == "medium"
        assert service._determine_urgency(info_rec) == "low"

    def test_effort_estimation(self) -> None:
        """Effort should be estimated based on recommendation content."""
        high_effort_rec = RecommendationItem(
            message="Major work required on coverage",
            category=RecommendationCategory.LOW_COVERAGE,
            severity="critical",
        )
        medium_effort_rec = RecommendationItem(
            message="Add measurable impact",
            category=RecommendationCategory.MISSING_METRIC,
            severity="warning",
        )
        low_effort_rec = RecommendationItem(
            message="Replace generic wording",
            category=RecommendationCategory.STRUCTURE_IMPROVEMENT,
            severity="info",
        )

        service = RecommendationPrioritizationService()

        assert service._estimate_effort(high_effort_rec) == "high"
        assert service._estimate_effort(medium_effort_rec) == "medium"
        assert service._estimate_effort(low_effort_rec) == "low"