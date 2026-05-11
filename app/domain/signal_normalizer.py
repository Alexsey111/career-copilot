from __future__ import annotations

from typing import Callable, Protocol

from app.config.calibration import CALIBRATION_PROFILES, CALIBRATION_VERSIONS
from app.domain.normalized_signals import NormalizedSignal, SignalType, SignalTaxonomy
from app.domain.signals import UnifiedSignal


class Calibrator(Protocol):
    """Protocol for signal calibrators."""

    def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
        """Calibrate a raw score to normalized distribution."""
        ...


class SignalConfidenceModel:
    """Model to estimate signal confidence from metadata and source information."""

    def estimate(
        self,
        signal_type: SignalType,
        raw_score: float,
        metadata: dict[str, object] | None,
        source_type: str,
        was_calibrated: bool,
    ) -> float:
        """Compute confidence from data completeness, evidence strength and source type."""
        completeness = self._estimate_data_completeness(metadata)
        evidence_strength = self._estimate_evidence_strength(metadata)
        source_bonus = self._estimate_source_bonus(source_type)

        base = 0.2 + 0.45 * completeness + 0.25 * evidence_strength + source_bonus
        if was_calibrated:
            base += 0.05

        # Signals with very low raw score should not be overconfident
        if raw_score < 0.2:
            base -= 0.1

        return max(0.0, min(1.0, base))

    def _estimate_data_completeness(self, metadata: dict[str, object] | None) -> float:
        if not metadata:
            return 0.5

        completeness = 0.5
        if "score_count" in metadata and isinstance(metadata["score_count"], int):
            completeness = min(1.0, 0.2 + metadata["score_count"] * 0.08)

        if "total_requirements" in metadata and "supported_count" in metadata:
            total = metadata["total_requirements"]
            supported = metadata["supported_count"]
            if isinstance(total, int) and isinstance(supported, int) and total > 0:
                completeness = max(completeness, min(1.0, supported / total))

        if "coverage_strength" in metadata and isinstance(metadata["coverage_strength"], float):
            completeness = max(completeness, metadata["coverage_strength"])

        return min(1.0, completeness)

    def _estimate_evidence_strength(self, metadata: dict[str, object] | None) -> float:
        if not metadata:
            return 0.5

        strength = metadata.get("evidence_strength")
        if isinstance(strength, str):
            mapping = {
                "strong": 0.95,
                "moderate": 0.75,
                "weak": 0.5,
                "missing": 0.3,
            }
            return mapping.get(strength.lower(), 0.5)

        quality_scores = metadata.get("quality_scores")
        if isinstance(quality_scores, list) and quality_scores:
            numeric = [score for score in quality_scores if isinstance(score, (int, float))]
            if numeric:
                return min(1.0, sum(numeric) / len(numeric))

        return 0.5

    def _estimate_source_bonus(self, source_type: str) -> float:
        if not source_type:
            return 0.0

        structured_sources = {"coverage_mapping", "ats_keyword_preservation", "interview_answers"}
        semantic_sources = {"evidence_quality", "interview_answers"}

        if source_type in structured_sources:
            return 0.05
        if source_type in semantic_sources:
            return 0.1
        return 0.0


class SignalContractNormalizer:
    """Normalizer that converts UnifiedSignals to canonical NormalizedSignals with calibration."""

    def __init__(self, calibration_profile: str = "v1.0") -> None:
        self._calibrators: dict[SignalType, Calibrator] = {}
        self._confidence_model = SignalConfidenceModel()
        self._calibration_profile = calibration_profile

        # Register default calibrators based on profile
        self._register_default_calibrators()

    def register_calibrator(self, signal_type: SignalType, calibrator: Calibrator) -> None:
        """Register a calibrator for a signal type."""
        self._calibrators[signal_type] = calibrator

    def normalize_signal(self, signal: UnifiedSignal) -> NormalizedSignal:
        """Convert UnifiedSignal to NormalizedSignal with calibration."""
        signal_type = self._map_signal_type(signal.signal_type)
        taxonomy = NormalizedSignal.taxonomy_for_type(signal_type)

        # Apply calibration if available
        calibrated_value = signal.score
        if signal_type in self._calibrators:
            calibrated_value = self._calibrators[signal_type].calibrate(
                signal.score,
                signal.metadata
            )

        was_calibrated = calibrated_value != signal.score
        confidence = self._confidence_model.estimate(
            signal_type=signal_type,
            raw_score=signal.score,
            metadata=signal.metadata,
            source_type=signal.source,
            was_calibrated=was_calibrated,
        )

        return NormalizedSignal(
            type=signal_type,
            taxonomy=taxonomy,
            value=round(calibrated_value, 3),
            confidence=round(confidence, 3),
            calibrated=was_calibrated,
            calibration_version=self._calibration_profile,
            source_signal_ids=[signal.signal_id] if signal.signal_id else [],
        )

    def normalize_signals(self, signals: list[UnifiedSignal]) -> list[NormalizedSignal]:
        """Normalize a list of UnifiedSignals."""
        return [self.normalize_signal(signal) for signal in signals]

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
        return mapping.get(signal_type_str, SignalType.QUALITY)  # Default to QUALITY

    def _register_default_calibrators(self) -> None:
        """Register default calibrators for each signal type based on calibration profile."""
        profiles = CALIBRATION_VERSIONS.get(self._calibration_profile, CALIBRATION_PROFILES)

        # Coverage calibrator: normalize based on typical distributions
        class CoverageCalibrator:
            def __init__(self, profile: dict[str, object]) -> None:
                self.low_boost = profile.get("low_boost", 1.2)
                self.high_damping = profile.get("high_damping", 0.95)
                self.mid_range = profile.get("mid_range", (0.3, 0.8))

            def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
                if raw_score < self.mid_range[0]:
                    return min(1.0, raw_score * self.low_boost)
                if raw_score > self.mid_range[1]:
                    return min(1.0, raw_score * self.high_damping)
                return raw_score

        # Evidence calibrator: normalize based on quality assessment patterns
        class EvidenceCalibrator:
            def __init__(self, profile: dict[str, object]) -> None:
                self.quality_adjustment = profile.get("quality_adjustment", 0.9)
                self.baseline_offset = profile.get("baseline_offset", 0.05)
                self.use_quality_distribution = profile.get("use_quality_distribution", True)

            def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
                if metadata and self.use_quality_distribution and "quality_distribution" in metadata:
                    return raw_score
                return max(0.0, min(1.0, raw_score * self.quality_adjustment + self.baseline_offset))

        # ATS calibrator: normalize keyword matching scores
        class ATSCalibrator:
            def __init__(self, profile: dict[str, object]) -> None:
                self.keyword_penalty = profile.get("keyword_penalty", 0.9)

            def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
                return max(0.0, min(1.0, raw_score * self.keyword_penalty))

        # Interview calibrator: normalize based on answer quality
        class InterviewCalibrator:
            def __init__(self, profile: dict[str, object]) -> None:
                self.low_boost = profile.get("low_boost", 1.1)
                self.high_damping = profile.get("high_damping", 0.95)
                self.threshold = profile.get("threshold", 0.4)

            def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
                if raw_score < self.threshold:
                    return max(0.0, raw_score * self.low_boost)
                return max(0.0, min(1.0, raw_score * self.high_damping))

        # Quality calibrator: composite score normalization
        class QualityCalibrator:
            def __init__(self, profile: dict[str, object]) -> None:
                self.composite_factor = profile.get("composite_factor", 0.85)
                self.baseline_offset = profile.get("baseline_offset", 0.075)

            def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
                return max(0.0, min(1.0, raw_score * self.composite_factor + self.baseline_offset))

        # Readiness calibrator: behavioral signal normalization
        class ReadinessCalibrator:
            def __init__(self, profile: dict[str, object]) -> None:
                self.behavioral_factor = profile.get("behavioral_factor", 0.9)

            def calibrate(self, raw_score: float, metadata: dict[str, object] | None = None) -> float:
                return max(0.0, min(1.0, raw_score * self.behavioral_factor))

        self.register_calibrator(SignalType.COVERAGE, CoverageCalibrator(profiles.get(SignalType.COVERAGE, {})))
        self.register_calibrator(SignalType.EVIDENCE, EvidenceCalibrator(profiles.get(SignalType.EVIDENCE, {})))
        self.register_calibrator(SignalType.ATS, ATSCalibrator(profiles.get(SignalType.ATS, {})))
        self.register_calibrator(SignalType.INTERVIEW, InterviewCalibrator(profiles.get(SignalType.INTERVIEW, {})))
        self.register_calibrator(SignalType.QUALITY, QualityCalibrator(profiles.get(SignalType.QUALITY, {})))
        self.register_calibrator(SignalType.READINESS, ReadinessCalibrator(profiles.get(SignalType.READINESS, {})))