from __future__ import annotations

from app.domain.readiness_models import RecommendationItem
from app.domain.recommendation_models import PrioritizedRecommendation, RecommendationImpact


class RecommendationPrioritizationService:
    """Service for prioritizing recommendations based on impact, urgency, and effort."""

    # Urgency weights (higher = more urgent)
    URGENCY_WEIGHTS = {
        "high": 1.0,
        "medium": 0.7,
        "low": 0.4,
    }

    # Effort weights (higher = more effort required)
    EFFORT_WEIGHTS = {
        "high": 1.0,
        "medium": 0.7,
        "low": 0.4,
    }

    # Impact estimation based on recommendation patterns
    IMPACT_PATTERNS = {
        "critical": {
            "score_delta": 0.15,
            "confidence": 0.9,
            "components": ["coverage", "evidence", "ats"],
        },
        "blocking": {
            "score_delta": 0.12,
            "confidence": 0.85,
            "components": ["coverage", "evidence"],
        },
        "quality": {
            "score_delta": 0.08,
            "confidence": 0.75,
            "components": ["quality", "evidence"],
        },
        "action": {
            "score_delta": 0.10,
            "confidence": 0.8,
            "components": ["coverage", "ats"],
        },
        "ready": {
            "score_delta": 0.0,
            "confidence": 1.0,
            "components": [],
        },
    }

    def prioritize_recommendations(
        self,
        recommendations: list[RecommendationItem],
    ) -> list[PrioritizedRecommendation]:
        """Prioritize recommendations based on impact, urgency, and effort."""
        prioritized: list[PrioritizedRecommendation] = []

        for rec in recommendations:
            impact = self._analyze_impact(rec)
            urgency = self._determine_urgency(rec)
            effort = self._estimate_effort(rec)
            priority_score = self._calculate_priority_score(impact, urgency, effort)

            prioritized.append(PrioritizedRecommendation(
                recommendation=rec,
                impact=impact,
                urgency=urgency,
                effort=effort,
                priority_score=priority_score,
            ))

        # Sort by priority score descending (highest first)
        prioritized.sort(key=lambda x: x.priority_score, reverse=True)

        return prioritized

    def get_top_recommendations(
        self,
        recommendations: list[RecommendationItem],
        limit: int = 3,
    ) -> list[PrioritizedRecommendation]:
        """Get top N prioritized recommendations."""
        prioritized = self.prioritize_recommendations(recommendations)
        return prioritized[:limit]

    def _analyze_impact(self, recommendation: RecommendationItem) -> RecommendationImpact:
        """Analyze the estimated impact of a recommendation."""
        pattern = self.IMPACT_PATTERNS.get(recommendation.category, {
            "score_delta": 0.05,
            "confidence": 0.6,
            "components": ["quality"],
        })

        # Adjust based on severity
        severity_multiplier = {
            "critical": 1.2,
            "warning": 1.0,
            "info": 0.8,
        }.get(recommendation.severity, 1.0)

        score_delta = pattern["score_delta"] * severity_multiplier

        return RecommendationImpact(
            score_delta_estimate=round(score_delta, 3),
            affected_components=pattern["components"],
            confidence=pattern["confidence"],
        )

    def _determine_urgency(self, recommendation: RecommendationItem) -> str:
        """Determine urgency level based on recommendation characteristics."""
        if recommendation.severity == "critical":
            return "high"
        elif recommendation.severity == "warning":
            return "medium"
        elif "blocking" in recommendation.message.lower() or "critical" in recommendation.message.lower():
            return "high"
        elif "significant" in recommendation.message.lower():
            return "medium"
        else:
            return "low"

    def _estimate_effort(self, recommendation: RecommendationItem) -> str:
        """Estimate effort required to implement the recommendation."""
        message_lower = recommendation.message.lower()

        # High effort indicators
        if any(keyword in message_lower for keyword in [
            "major work", "significant improvements", "complete rewrite",
            "rebuild", "redesign", "extensive"
        ]):
            return "high"

        # Medium effort indicators
        if any(keyword in message_lower for keyword in [
            "add measurable", "improve star", "expand coverage",
            "enhance evidence", "refine keywords"
        ]):
            return "medium"

        # Low effort indicators (default)
        if any(keyword in message_lower for keyword in [
            "replace generic", "improve wording", "minor adjustments",
            "small changes", "tweak"
        ]):
            return "low"

        # Default based on category
        category_effort = {
            "critical": "high",
            "blocking": "medium",
            "quality": "low",
            "action": "medium",
            "ready": "low",
        }
        return category_effort.get(recommendation.category, "medium")

    def _calculate_priority_score(self, impact: RecommendationImpact, urgency: str, effort: str) -> float:
        """Calculate priority score combining impact, urgency, and effort."""
        urgency_weight = self.URGENCY_WEIGHTS.get(urgency, 0.5)
        effort_weight = self.EFFORT_WEIGHTS.get(effort, 0.7)

        # Priority = Impact * Urgency / Effort
        # Higher impact, higher urgency, lower effort = higher priority
        priority = (impact.score_delta_estimate * urgency_weight) / effort_weight

        return round(priority, 3)