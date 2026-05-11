from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List


class TrajectoryClassification(Enum):
    """Classification of candidate evaluation trajectory."""
    IMPROVING = "improving"
    STAGNATING = "stagnating"
    UNSTABLE = "unstable"
    REGRESSING = "regressing"
    ACCELERATING = "accelerating"


class SignalStability(Enum):
    """Stability classification for individual signals."""
    CONSISTENT = "consistent"
    IMPROVING = "improving"
    DETERIORATING = "deteriorating"
    VOLATILE = "volatile"


@dataclass(slots=True)
class TrajectoryTrend:
    """Trend analysis for a candidate's evaluation trajectory."""
    candidate_id: str
    classification: TrajectoryClassification
    confidence: float  # Confidence in the classification
    trend_strength: float  # Strength of the trend (0.0-1.0)
    analysis_period_days: int
    snapshot_count: int

    # Trend metrics
    average_score: float
    score_volatility: float  # Standard deviation of scores
    recent_momentum: float  # Recent score change rate
    overall_trend_slope: float  # Linear trend slope

    # Stability indicators
    stability_score: float  # Overall stability (0.0-1.0, higher = more stable)
    confidence_trend: float  # Trend in confidence levels

    analyzed_at: datetime


@dataclass(slots=True)
class SignalTrend:
    """Trend analysis for individual signals."""
    signal_type: str
    stability: SignalStability
    persistence_days: int  # How long this signal has been tracked
    snapshot_count: int

    # Trend metrics
    current_value: float
    average_value: float
    value_volatility: float
    recent_change: float  # Change in last N snapshots

    # Stability metrics
    confidence_average: float
    confidence_volatility: float

    # Weakness detection
    is_persistent_weakness: bool
    weakness_duration_days: int
    weakness_threshold: float  # Threshold below which considered weak


@dataclass(slots=True)
class RecommendationOutcome:
    """Analysis of recommendation effectiveness."""
    recommendation_id: str
    candidate_id: str

    # Recommendation metadata
    issued_at: datetime
    recommendation_type: str
    target_signals: List[str]  # Signals this recommendation aimed to improve

    # Outcome metrics
    readiness_delta: float  # Change in readiness score after recommendation
    signal_improvements: Dict[str, float]  # Signal -> improvement amount
    time_to_impact_days: int  # Days until impact was observed

    # Effectiveness classification
    effectiveness_score: float  # 0.0-1.0, higher = more effective
    was_followed: bool  # Whether recommendation was acted upon (if known)

    # Attribution
    attributable_readiness_change: float  # Portion of readiness change attributable to this rec


@dataclass(slots=True)
class CandidateMomentum:
    """Current momentum and trajectory momentum for a candidate."""
    candidate_id: str
    current_readiness: float
    trajectory_classification: TrajectoryClassification

    # Momentum indicators
    short_term_momentum: float  # Last 3 snapshots
    medium_term_momentum: float  # Last 10 snapshots
    long_term_momentum: float  # All available history

    # Risk indicators
    regression_risk: float  # Probability of regression
    stagnation_risk: float  # Probability of stagnation
    volatility_risk: float  # Risk of unstable performance

    analyzed_at: datetime

    # Key insights
    critical_weaknesses: List[str] = field(default_factory=list)
    recent_improvements: List[str] = field(default_factory=list)
    recommended_focus_areas: List[str] = field(default_factory=list)