from __future__ import annotations

from typing import Callable, Protocol

from app.domain.normalized_signals import NormalizedSignal, SignalType
from app.domain.signal_normalizer import SignalContractNormalizer
from app.domain.signals import UnifiedSignal


class ScoringFunction(Protocol):
    """Protocol for scoring functions that process signals."""

    def __call__(self, signals: list[UnifiedSignal]) -> float:
        """Process signals and return a score."""
        ...


class Calibrator(Protocol):
    """Protocol for signal calibrators."""

    def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
        """Calibrate a raw score to normalized distribution."""
        ...


class Aggregator(Protocol):
    """Protocol for aggregating normalized signals."""

    def aggregate(self, signals: list[NormalizedSignal]) -> float:
        """Aggregate normalized signals into final score."""
        ...


class ScoringRegistry:
    """Two-level registry for managing scoring functions, calibrators, and aggregators."""

    def __init__(self) -> None:
        self._scorers: dict[SignalType, ScoringFunction] = {}
        self._calibrators: dict[SignalType, Calibrator] = {}
        self._aggregator: Aggregator | None = None
        self._signal_weights: dict[SignalType, float] = {}

    def register_scorer(self, signal_type: SignalType, scorer: ScoringFunction) -> None:
        """Register a scoring function for a signal type."""
        self._scorers[signal_type] = scorer

    def register_calibrator(self, signal_type: SignalType, calibrator: Calibrator) -> None:
        """Register a calibrator for a signal type."""
        self._calibrators[signal_type] = calibrator

    def set_aggregator(self, aggregator: Aggregator) -> None:
        """Set the global aggregator for combining normalized signals."""
        self._aggregator = aggregator

    def set_signal_weight(self, signal_type: SignalType, weight: float) -> None:
        """Set the weight for a signal type."""
        self._signal_weights[signal_type] = weight

    def get_signal_weight(self, signal_type: SignalType) -> float:
        """Get the weight for a signal type."""
        return self._signal_weights.get(signal_type, 1.0)

    def process_signals(self, signals: list[UnifiedSignal], calibration_profile: str = "v1.0") -> dict[str, float]:
        """
        Complete processing pipeline: score → calibrate → aggregate.
        Returns score, confidence, and variance.
        
        Args:
            signals: List of unified signals to process
            calibration_profile: Version of calibration to use (e.g., "v1.0")
        """
        raw_scores = self._score_signals(signals)
        calibrated_signals = self._calibrate_scores(raw_scores, signals, calibration_profile)

        if self._aggregator:
            score = self._aggregator.aggregate(calibrated_signals)
        else:
            score = self._default_aggregate(calibrated_signals)

        confidence = self._aggregate_confidence(calibrated_signals)
        variance = self._calculate_variance(calibrated_signals, score)

        return {
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "variance": round(variance, 6),
        }

    def _score_signals(self, signals: list[UnifiedSignal]) -> dict[SignalType, float]:
        """Score signals by type using registered scorers."""
        scores_by_type: dict[SignalType, float] = {}

        signals_by_type: dict[str, list[UnifiedSignal]] = {}
        for signal in signals:
            signal_type_str = signal.signal_type
            if signal_type_str not in signals_by_type:
                signals_by_type[signal_type_str] = []
            signals_by_type[signal_type_str].append(signal)

        for signal_type_str, type_signals in signals_by_type.items():
            signal_type = self._map_signal_type(signal_type_str)
            if signal_type in self._scorers:
                scores_by_type[signal_type] = self._scorers[signal_type](type_signals)
            else:
                if type_signals:
                    scores_by_type[signal_type] = sum(s.score for s in type_signals) / len(type_signals)

        return scores_by_type

    def _calibrate_scores(
        self,
        raw_scores: dict[SignalType, float],
        original_signals: list[UnifiedSignal],
        calibration_profile: str = "v1.0",
    ) -> list[NormalizedSignal]:
        """Calibrate raw scores using registered calibrators."""
        # Use normalizer for calibration with the specified profile
        normalizer = SignalContractNormalizer(calibration_profile)
        
        # Create synthetic UnifiedSignals for normalization
        synthetic_signals = []
        for signal_type, raw_score in raw_scores.items():
            # Find original signal metadata
            metadata = {}
            for orig_signal in original_signals:
                if self._map_signal_type(orig_signal.signal_type) == signal_type:
                    metadata = orig_signal.metadata or {}
                    break
            
            synthetic_signal = UnifiedSignal(
                signal_type=signal_type.value,
                score=raw_score,
                weight=1.0,  # Not used in normalization
                source="scoring_registry",
                metadata=metadata,
                signal_id=f"synthetic_{signal_type.value}_{hash(str(raw_score))}",
            )
            synthetic_signals.append(synthetic_signal)
        
        # Normalize signals using the normalizer
        return normalizer.normalize_signals(synthetic_signals)

    def _default_aggregate(self, signals: list[NormalizedSignal]) -> float:
        """Default aggregation: weighted average of effective scores."""
        if not signals:
            return 0.0

        total_weighted_score = 0.0
        total_weight = 0.0

        for signal in signals:
            weight = self.get_signal_weight(signal.type)
            effective_score = signal.effective_score
            total_weighted_score += effective_score * weight
            total_weight += weight

        return total_weighted_score / total_weight if total_weight > 0 else 0.0

    def _aggregate_confidence(self, signals: list[NormalizedSignal]) -> float:
        """Aggregate confidence across normalized signals."""
        if not signals:
            return 0.0

        total_weight = 0.0
        weighted_confidence = 0.0
        for signal in signals:
            weight = self.get_signal_weight(signal.type)
            weighted_confidence += signal.confidence * weight
            total_weight += weight

        return weighted_confidence / total_weight if total_weight > 0 else 0.0

    def _calculate_variance(self, signals: list[NormalizedSignal], mean_score: float) -> float:
        """Calculate variance of effective signal scores."""
        if not signals:
            return 0.0

        total_weight = 0.0
        variance_sum = 0.0
        for signal in signals:
            weight = self.get_signal_weight(signal.type)
            diff = signal.effective_score - mean_score
            variance_sum += weight * (diff ** 2)
            total_weight += weight

        return variance_sum / total_weight if total_weight > 0 else 0.0

    def _map_signal_type(self, signal_type_str: str) -> SignalType:
        """Map string signal type to SignalType enum."""
        mapping = {
            "coverage": SignalType.COVERAGE,
            "evidence": SignalType.EVIDENCE,
            "ats": SignalType.ATS,
            "interview": SignalType.INTERVIEW,
            "quality": SignalType.QUALITY,
            "readiness": SignalType.READINESS,
        }
        return mapping.get(signal_type_str, SignalType.QUALITY)

    def _estimate_confidence(
        self,
        signal_type: SignalType,
        metadata: dict[str, object] | None,
        was_calibrated: bool,
    ) -> float:
        """Estimate confidence in the calibrated signal."""
        base_confidence = 0.8

        if metadata:
            if "score_count" in metadata:
                count = metadata["score_count"]
                if isinstance(count, int):
                    base_confidence = min(0.95, 0.7 + count * 0.05)

        if was_calibrated:
            base_confidence += 0.1

        return max(0.1, min(1.0, base_confidence))

    @property
    def registered_types(self) -> list[SignalType]:
        """Get list of registered signal types."""
        return list(self._scorers.keys())