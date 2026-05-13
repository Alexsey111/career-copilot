# app\domain\recommendation_models.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.domain.readiness_models import RecommendationItem


class RecommendationTaskType(Enum):
    """Types of actionable recommendation tasks."""
    ADD_METRIC = "add_metric"
    ADD_EVIDENCE = "add_evidence"
    IMPROVE_DESCRIPTION = "improve_description"
    ADD_QUANTIFIABLE_RESULT = "add_quantifiable_result"
    ADD_TIMEFRAME = "add_timeframe"
    ADD_CONTEXT = "add_context"
    SPLIT_ACHIEVEMENT = "split_achievement"
    MERGE_ACHIEVEMENTS = "merge_achievements"
    ADD_SKILL_KEYWORD = "add_skill_keyword"
    REMOVE_REDUNDANT = "remove_redundant"


class RecommendationPriority(Enum):
    """Priority levels for recommendation tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class RecommendationTask:
    """Actionable task derived from recommendation analysis."""
    task_type: RecommendationTaskType
    target_achievement_id: Optional[str] = None
    target_signal_type: Optional[str] = None

    # Task properties
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    blocking: bool = False

    # Human-readable description
    description: str = ""
    rationale: str = ""

    # Estimated impact with confidence
    estimated_score_improvement: float = 0.0
    confidence: float = 0.0

    # Additional context
    metadata: dict = field(default_factory=dict)

    # Links to related items
    related_recommendation_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RecommendationImpact:
    score_delta_estimate: float
    affected_components: list[str]
    confidence: float


@dataclass(slots=True)
class PrioritizedRecommendation:
    recommendation: RecommendationItem

    impact: RecommendationImpact

    urgency: str
    effort: str

    priority_score: float