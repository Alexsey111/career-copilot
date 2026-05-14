from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev
from typing import Dict, List, Protocol, Tuple

from app.domain.analytics_models import (
    CandidateMomentum,
    RecommendationOutcome,
    SignalStability,
    SignalTrend,
    TrajectoryClassification,
    TrajectoryTrend,
)
from app.domain.evaluation_models import EvaluationSnapshot
from app.repositories.evaluation_repository import EvaluationRepository


class EvaluationAnalyticsService(Protocol):
    """Service for analyzing evaluation trajectories and generating insights."""

    @abstractmethod
    def analyze_trajectory(self, candidate_id: str, days_back: int = 30) -> TrajectoryTrend:
        """Analyze the trajectory trend for a candidate."""
        ...

    @abstractmethod
    def analyze_signal_trends(self, candidate_id: str, days_back: int = 30) -> List[SignalTrend]:
        """Analyze trends for individual signals."""
        ...

    @abstractmethod
    def analyze_recommendation_outcomes(
        self, candidate_id: str, recommendation_ids: List[str] | None = None
    ) -> List[RecommendationOutcome]:
        """Analyze effectiveness of recommendations."""
        ...

    @abstractmethod
    def calculate_momentum(self, candidate_id: str) -> CandidateMomentum:
        """Calculate current momentum and trajectory insights."""
        ...


class DefaultEvaluationAnalyticsService:
    """Default implementation of evaluation analytics."""

    def __init__(self, repository: EvaluationRepository) -> None:
        self._repository = repository

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        """Normalize datetimes to UTC-aware values before comparisons."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def analyze_trajectory(self, candidate_id: str, days_back: int = 30) -> TrajectoryTrend:
        """Analyze the trajectory trend for a candidate."""
        snapshots = self._repository.get_snapshots_for_candidate(candidate_id, limit=50)

        if not snapshots:
            # Return default for no data
            return TrajectoryTrend(
                candidate_id=candidate_id,
                classification=TrajectoryClassification.STAGNATING,
                confidence=0.0,
                trend_strength=0.0,
                analysis_period_days=days_back,
                snapshot_count=0,
                average_score=0.0,
                score_volatility=0.0,
                recent_momentum=0.0,
                overall_trend_slope=0.0,
                stability_score=0.0,
                confidence_trend=0.0,
                analyzed_at=datetime.now(timezone.utc),
            )

        # Filter by time period
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        recent_snapshots = [
            s for s in snapshots
            if self._ensure_utc(s.created_at) >= cutoff_date
        ]

        if not recent_snapshots:
            recent_snapshots = snapshots[:5]  # Use most recent if none in period

        # Sort by creation time
        recent_snapshots.sort(key=lambda s: self._ensure_utc(s.created_at))

        scores = [s.readiness_score for s in recent_snapshots]
        confidences = [s.confidence for s in recent_snapshots]

        # Calculate metrics
        average_score = mean(scores) if scores else 0.0
        score_volatility = stdev(scores) if len(scores) > 1 else 0.0
        stability_score = max(0.0, 1.0 - score_volatility)  # Higher stability = lower volatility

        # Trend slope (simple linear regression)
        overall_trend_slope = self._calculate_trend_slope(recent_snapshots)

        # Recent momentum (last 3 vs previous 3)
        recent_momentum = self._calculate_recent_momentum(recent_snapshots)

        # Confidence trend
        confidence_trend = self._calculate_trend_slope_from_points([(s.created_at, s.confidence) for s in recent_snapshots])

        # Classification
        classification, confidence, trend_strength = self._classify_trajectory(
            overall_trend_slope, score_volatility, recent_momentum, stability_score
        )

        return TrajectoryTrend(
            candidate_id=candidate_id,
            classification=classification,
            confidence=confidence,
            trend_strength=trend_strength,
            analysis_period_days=days_back,
            snapshot_count=len(recent_snapshots),
            average_score=round(average_score, 3),
            score_volatility=round(score_volatility, 3),
            recent_momentum=round(recent_momentum, 3),
            overall_trend_slope=round(overall_trend_slope, 3),
            stability_score=round(stability_score, 3),
            confidence_trend=round(confidence_trend, 3),
            analyzed_at=datetime.now(timezone.utc),
        )

    def analyze_signal_trends(self, candidate_id: str, days_back: int = 30) -> List[SignalTrend]:
        """Analyze trends for individual signals."""
        snapshots = self._repository.get_snapshots_for_candidate(candidate_id, limit=50)

        if not snapshots:
            return []

        # Group signals by type
        signal_history: Dict[str, List[tuple]] = {}  # signal_type -> [(date, value, confidence)]

        for snapshot in snapshots:
            for signal in snapshot.normalized_signals:
                if signal.type.value not in signal_history:
                    signal_history[signal.type.value] = []
                signal_history[signal.type.value].append((
                    self._ensure_utc(snapshot.created_at),
                    signal.value,
                    signal.confidence
                ))

        trends = []
        for signal_type, history in signal_history.items():
            if not history:
                continue

            # Sort by date
            history.sort(key=lambda x: x[0])

            # Filter by time period
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            recent_history = [h for h in history if h[0] >= cutoff_date]

            if not recent_history:
                recent_history = history[-10:]  # Use last 10 if none recent

            values = [h[1] for h in recent_history]
            confidences = [h[2] for h in recent_history]

            current_value = values[-1] if values else 0.0
            average_value = mean(values) if values else 0.0
            value_volatility = stdev(values) if len(values) > 1 else 0.0

            confidence_average = mean(confidences) if confidences else 0.0
            confidence_volatility = stdev(confidences) if len(confidences) > 1 else 0.0

            # Recent change (last half vs first half)
            recent_change = 0.0
            if len(values) >= 2:
                mid = len(values) // 2
                early_avg = mean(values[:mid]) if mid > 0 else values[0]
                late_avg = mean(values[mid:]) if mid < len(values) else values[-1]
                recent_change = late_avg - early_avg

            # Weakness detection
            weakness_threshold = 0.6  # Configurable
            is_weak = current_value < weakness_threshold
            persistent_weak = all(v < weakness_threshold for v in values[-5:]) if len(values) >= 5 else False
            weakness_duration = len([v for v in values if v < weakness_threshold])

            # Stability classification
            stability = self._classify_signal_stability(value_volatility, recent_change)

            trends.append(SignalTrend(
                signal_type=signal_type,
                stability=stability,
                persistence_days=(recent_history[-1][0] - recent_history[0][0]).days if len(recent_history) > 1 else 0,
                snapshot_count=len(recent_history),
                current_value=round(current_value, 3),
                average_value=round(average_value, 3),
                value_volatility=round(value_volatility, 3),
                recent_change=round(recent_change, 3),
                confidence_average=round(confidence_average, 3),
                confidence_volatility=round(confidence_volatility, 3),
                is_persistent_weakness=persistent_weak,
                weakness_duration_days=weakness_duration,
                weakness_threshold=weakness_threshold,
            ))

        return trends

    def analyze_recommendation_outcomes(
        self, candidate_id: str, recommendation_ids: List[str] | None = None
    ) -> List[RecommendationOutcome]:
        """Analyze effectiveness of recommendations."""
        # This would require linking recommendations to snapshots
        # For now, return empty list as implementation depends on recommendation tracking
        return []

    def calculate_momentum(self, candidate_id: str) -> CandidateMomentum:
        """Calculate current momentum and trajectory insights."""
        trajectory = self.analyze_trajectory(candidate_id, days_back=30)
        signal_trends = self.analyze_signal_trends(candidate_id, days_back=30)
        snapshots = self._repository.get_snapshots_for_candidate(candidate_id, limit=15)

        if not snapshots:
            return CandidateMomentum(
                candidate_id=candidate_id,
                current_readiness=0.0,
                trajectory_classification=TrajectoryClassification.STAGNATING,
                short_term_momentum=0.0,
                medium_term_momentum=0.0,
                long_term_momentum=0.0,
                regression_risk=0.0,
                stagnation_risk=1.0,
                volatility_risk=0.0,
                analyzed_at=datetime.now(timezone.utc),
            )

        # Sort snapshots by time ascending for momentum calculations
        snapshots.sort(key=lambda s: self._ensure_utc(s.created_at))

        current_readiness = snapshots[-1].readiness_score

        # Calculate momentum at different time scales
        short_term_momentum = self._calculate_recent_momentum(snapshots[-3:])
        medium_term_momentum = self._calculate_recent_momentum(snapshots[-10:])
        long_term_momentum = self._calculate_recent_momentum(snapshots)

        # Risk calculations
        regression_risk = max(0.0, -long_term_momentum)  # Negative momentum = regression risk
        stagnation_risk = 1.0 - abs(long_term_momentum)  # Low momentum = stagnation risk
        volatility_risk = trajectory.score_volatility

        # Key insights
        critical_weaknesses = [t.signal_type for t in signal_trends if t.is_persistent_weakness]
        recent_improvements = [t.signal_type for t in signal_trends if t.recent_change > 0.1]
        recommended_focus_areas = critical_weaknesses  # For now, focus on weaknesses

        return CandidateMomentum(
            candidate_id=candidate_id,
            current_readiness=round(current_readiness, 3),
            trajectory_classification=trajectory.classification,
            short_term_momentum=round(short_term_momentum, 3),
            medium_term_momentum=round(medium_term_momentum, 3),
            long_term_momentum=round(long_term_momentum, 3),
            regression_risk=round(regression_risk, 3),
            stagnation_risk=round(stagnation_risk, 3),
            volatility_risk=round(volatility_risk, 3),
            critical_weaknesses=critical_weaknesses,
            recent_improvements=recent_improvements,
            recommended_focus_areas=recommended_focus_areas,
                analyzed_at=datetime.now(timezone.utc),
        )

    def _calculate_trend_slope(self, snapshots: List[EvaluationSnapshot]) -> float:
        """Calculate linear trend slope for readiness scores."""
        if len(snapshots) < 2:
            return 0.0

        # Simple linear regression
        n = len(snapshots)
        x = list(range(n))  # Time indices
        y = [s.readiness_score for s in snapshots]

        x_mean = mean(x)
        y_mean = mean(y)

        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        denominator = sum((xi - x_mean) ** 2 for xi in x)

        return numerator / denominator if denominator != 0 else 0.0

    def _calculate_recent_momentum(self, snapshots: List[EvaluationSnapshot]) -> float:
        """Calculate recent momentum from last few snapshots."""
        if len(snapshots) < 3:
            return 0.0

        early_scores = [s.readiness_score for s in snapshots[:len(snapshots)//2]]
        late_scores = [s.readiness_score for s in snapshots[len(snapshots)//2:]]

        early_avg = mean(early_scores) if early_scores else 0.0
        late_avg = mean(late_scores) if late_scores else 0.0

        return late_avg - early_avg

    def _calculate_trend_slope_from_points(self, data_points: List[Tuple[datetime, float]]) -> float:
        """Calculate linear trend slope from timestamp-value pairs."""
        if len(data_points) < 2:
            return 0.0

        # Sort by timestamp
        data_points = sorted(data_points, key=lambda x: x[0])

        # Convert timestamps to days since first timestamp
        base_time = data_points[0][0]
        x = [(point[0] - base_time).total_seconds() / (24 * 3600) for point in data_points]
        y = [point[1] for point in data_points]

        x_mean = mean(x)
        y_mean = mean(y)

        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        denominator = sum((xi - x_mean) ** 2 for xi in x)

        return numerator / denominator if denominator != 0 else 0.0

    def _classify_trajectory(
        self, slope: float, volatility: float, momentum: float, stability: float
    ) -> tuple[TrajectoryClassification, float, float]:
        """Classify trajectory based on metrics."""
        # Simple classification logic
        if slope > 0.05 and momentum > 0.02:
            classification = TrajectoryClassification.ACCELERATING if slope > 0.1 else TrajectoryClassification.IMPROVING
            confidence = min(1.0, stability * 0.8 + 0.2)
            strength = min(1.0, slope * 10)
        elif slope < -0.05:
            classification = TrajectoryClassification.REGRESSING
            confidence = min(1.0, stability * 0.7 + 0.3)
            strength = min(1.0, abs(slope) * 10)
        elif volatility > 0.1:
            classification = TrajectoryClassification.UNSTABLE
            confidence = min(1.0, (1.0 - volatility) * 0.6 + 0.4)
            strength = volatility
        else:
            classification = TrajectoryClassification.STAGNATING
            confidence = min(1.0, stability * 0.9 + 0.1)
            strength = 1.0 - abs(slope)

        return classification, confidence, strength

    def _classify_signal_stability(self, volatility: float, recent_change: float) -> SignalStability:
        """Classify signal stability."""
        if volatility > 0.15:
            return SignalStability.VOLATILE
        elif recent_change > 0.05:
            return SignalStability.IMPROVING
        elif recent_change < -0.05:
            return SignalStability.DETERIORATING
        else:
            return SignalStability.CONSISTENT

    def _calculate_momentum_for_snapshots(self, snapshots: List[EvaluationSnapshot]) -> float:
        """Calculate momentum for a subset of snapshots."""
        if len(snapshots) < 2:
            return 0.0

        scores = [s.readiness_score for s in snapshots]
        return (scores[-1] - scores[0]) / len(scores)  # Average change per snapshot
