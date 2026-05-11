from app.domain.normalized_signals import NormalizedSignal, SignalTaxonomy, SignalType
from app.domain.signal_normalizer import SignalContractNormalizer
from app.domain.signals import UnifiedSignal
from app.domain.scoring_registry import ScoringRegistry


class TestNormalizedSignal:

    def test_normalized_signal_creation_and_validation(self) -> None:
        signal = NormalizedSignal(
            type=SignalType.COVERAGE,
            taxonomy=SignalTaxonomy.STRUCTURAL,
            value=0.85,
            confidence=0.9,
            calibrated=True,
        )

        assert signal.type == SignalType.COVERAGE
        assert signal.taxonomy == SignalTaxonomy.STRUCTURAL
        assert signal.value == 0.85
        assert signal.confidence == 0.9
        assert signal.calibrated is True
        assert signal.is_valid is True
        assert signal.effective_score == 0.85 * 0.9
        assert signal.calibration_version == "v1.0"  # default
        assert signal.source_signal_ids == []  # default

    def test_invalid_normalized_signal(self) -> None:
        signal = NormalizedSignal(
            type=SignalType.EVIDENCE,
            taxonomy=SignalTaxonomy.SEMANTIC,
            value=1.5,  # Invalid value > 1.0
            confidence=0.8,
            calibrated=False,
        )

        assert signal.is_valid is False


class TestSignalContractNormalizer:

    def test_normalize_unified_signal(self) -> None:
        normalizer = SignalContractNormalizer()

        unified_signal = UnifiedSignal(
            signal_type="coverage",
            score=0.8,
            weight=0.3,
            source="test",
            metadata={"score_count": 5},
        )

        normalized = normalizer.normalize_signal(unified_signal)

        normalized = normalizer.normalize_signal(unified_signal)

        assert normalized.type == SignalType.COVERAGE
        assert normalized.taxonomy == SignalTaxonomy.STRUCTURAL
        assert normalized.value <= 1.0
        assert 0.0 <= normalized.confidence <= 1.0
        assert normalized.calibration_version == "v1.0"
        assert isinstance(normalized.source_signal_ids, list)
        # Note: calibration may or may not be applied depending on score range

    def test_normalize_signals_batch(self) -> None:
        normalizer = SignalContractNormalizer()

        signals = [
            UnifiedSignal("coverage", 0.8, 0.3, "test1"),
            UnifiedSignal("evidence", 0.7, 0.25, "test2"),
        ]

        normalized = normalizer.normalize_signals(signals)

        assert len(normalized) == 2
        assert all(s.is_valid for s in normalized)
        # Some signals may be calibrated, some may not depending on their values

    def test_calibration_effects(self) -> None:
        normalizer = SignalContractNormalizer()

        # Test coverage calibration (boosts low scores)
        low_coverage = UnifiedSignal("coverage", 0.2, 0.3, "test")
        normalized_low = normalizer.normalize_signal(low_coverage)
        assert normalized_low.value > 0.2  # Should be boosted
        assert normalized_low.calibrated is True

        # Test ATS calibration (dampens high scores)
        high_ats = UnifiedSignal("ats", 0.95, 0.2, "test")
        normalized_high = normalizer.normalize_signal(high_ats)
        assert normalized_high.value < 0.95  # Should be dampened
        assert normalized_high.calibrated is True


class TestTwoLevelScoringRegistry:

    def test_two_level_processing_pipeline(self) -> None:
        registry = ScoringRegistry()

        # Register scorers
        def coverage_scorer(signals: list[UnifiedSignal]) -> float:
            return sum(s.score for s in signals) / len(signals)

        registry.register_scorer(SignalType.COVERAGE, coverage_scorer)

        # Register calibrators (using normalizer's default calibrators)
        normalizer = SignalContractNormalizer()
        registry.register_calibrator(SignalType.COVERAGE, normalizer._calibrators[SignalType.COVERAGE])

        # Set weights
        registry.set_signal_weight(SignalType.COVERAGE, 0.3)

        # Process signals
        signals = [
            UnifiedSignal("coverage", 0.8, 0.3, "test1"),
            UnifiedSignal("coverage", 0.9, 0.3, "test2"),
        ]

        result = registry.process_signals(signals)

        assert isinstance(result, dict)
        assert set(result.keys()) == {"score", "confidence", "variance"}
        assert 0.0 <= result["score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["variance"] >= 0.0
        # Should be calibrated and aggregated

    def test_registry_without_custom_aggregator_uses_default(self) -> None:
        registry = ScoringRegistry()

        # Register minimal setup
        def simple_scorer(signals: list[UnifiedSignal]) -> float:
            return 0.75

        registry.register_scorer(SignalType.COVERAGE, simple_scorer)
        registry.set_signal_weight(SignalType.COVERAGE, 0.5)

        signals = [UnifiedSignal("coverage", 0.8, 0.3, "test")]
        result = registry.process_signals(signals)

        # Should use default aggregation
        assert isinstance(result, dict)
        assert 0.0 <= result["score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["variance"] >= 0.0

    def test_calibration_profile_versioning(self) -> None:
        registry = ScoringRegistry()

        # Register minimal setup
        def simple_scorer(signals: list[UnifiedSignal]) -> float:
            return 0.75

        registry.register_scorer(SignalType.COVERAGE, simple_scorer)
        registry.set_signal_weight(SignalType.COVERAGE, 0.5)

        signals = [UnifiedSignal("coverage", 0.8, 0.3, "test")]
        
        # Test default profile
        result_v1 = registry.process_signals(signals, calibration_profile="v1.0")
        assert 0.0 <= result_v1["score"] <= 1.0
        assert isinstance(result_v1, dict)

        # Test with different profile (should work the same for now)
        result_v2 = registry.process_signals(signals, calibration_profile="v2.0")
        assert 0.0 <= result_v2["score"] <= 1.0
        assert isinstance(result_v2, dict)