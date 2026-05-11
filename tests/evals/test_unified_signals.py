from app.domain.normalized_signals import SignalType
from app.domain.signals import UnifiedSignal
from app.domain.scoring_registry import ScoringRegistry
from app.domain.signal_adapters import SignalMigrationAdapters
from app.domain.coverage_models import RequirementCoverage
from app.domain.coverage_eval_models import CoverageEvaluationReport
from app.domain.constants import CoverageType


class TestUnifiedSignal:

    def test_signal_creation_and_validation(self) -> None:
        signal = UnifiedSignal(
            signal_type="coverage",
            score=0.85,
            weight=0.30,
            source="coverage_mapping",
            metadata={"test": True},
        )

        assert signal.signal_type == "coverage"
        assert signal.score == 0.85
        assert signal.weight == 0.30
        assert signal.source == "coverage_mapping"
        assert signal.metadata == {"test": True}
        assert signal.is_valid is True
        assert signal.weighted_score == 0.85 * 0.30

    def test_invalid_signal(self) -> None:
        signal = UnifiedSignal(
            signal_type="test",
            score=1.5,  # Invalid score > 1.0
            weight=-0.1,  # Invalid negative weight
            source="test",
        )

        assert signal.is_valid is False


class TestScoringRegistry:

    def test_registry_registration_and_scoring(self) -> None:
        registry = ScoringRegistry()

        # Register a simple scorer that averages coverage signals
        def average_scorer(signals: list[UnifiedSignal]) -> float:
            return sum(s.score for s in signals) / len(signals) if signals else 0.0

        registry.register_scorer(SignalType.COVERAGE, average_scorer)
        registry.set_signal_weight(SignalType.COVERAGE, 0.30)

        signals = [
            UnifiedSignal("coverage", 0.8, 0.30, "test1"),
            UnifiedSignal("coverage", 0.9, 0.30, "test2"),
            UnifiedSignal("evidence", 0.7, 0.25, "test3"),
        ]

        result = registry.process_signals(signals)

        assert isinstance(result, dict)
        assert "score" in result and "confidence" in result and "variance" in result
        assert 0.0 <= result["score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["variance"] >= 0.0

    def test_overall_score_calculation(self) -> None:
        registry = ScoringRegistry()

        registry.set_signal_weight(SignalType.COVERAGE, 0.30)
        registry.set_signal_weight(SignalType.EVIDENCE, 0.25)
        registry.set_signal_weight(SignalType.ATS, 0.20)

        signals = [
            UnifiedSignal("coverage", 0.8, 0.30, "test"),
            UnifiedSignal("evidence", 0.7, 0.25, "test"),
            UnifiedSignal("ats", 0.9, 0.20, "test"),
        ]

        result = registry.process_signals(signals)

        assert isinstance(result, dict)
        assert 0.0 <= result["score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["variance"] >= 0.0


class TestSignalMigrationAdapters:

    def test_coverage_adapter(self) -> None:
        coverage = [
            RequirementCoverage(
                requirement_text="req1",
                keyword="test",
                coverage_type=CoverageType.DIRECT,
            ),
            RequirementCoverage(
                requirement_text="req2",
                keyword="test",
                coverage_type=CoverageType.UNSUPPORTED,
            ),
        ]

        signals = SignalMigrationAdapters.from_coverage_requirements(coverage)

        assert len(signals) == 1
        assert signals[0].signal_type == "coverage"
        assert signals[0].score == 0.5  # 1 supported out of 2
        assert signals[0].weight == 0.30

    def test_evidence_adapter(self) -> None:
        evidence_scores = [0.8, 0.9, 0.7]

        signals = SignalMigrationAdapters.from_evidence_scores(evidence_scores)

        assert len(signals) == 1
        assert signals[0].signal_type == "evidence"
        assert signals[0].score == 0.8  # (0.8 + 0.9 + 0.7) / 3
        assert signals[0].weight == 0.25

    def test_ats_adapter(self) -> None:
        signals = SignalMigrationAdapters.from_ats_score(0.85)

        assert len(signals) == 1
        assert signals[0].signal_type == "ats"
        assert signals[0].score == 0.85
        assert signals[0].weight == 0.20

    def test_interview_adapter(self) -> None:
        signals = SignalMigrationAdapters.from_interview_score(0.75)

        assert len(signals) == 1
        assert signals[0].signal_type == "interview"
        assert signals[0].score == 0.75
        assert signals[0].weight == 0.15

    def test_quality_signal_creation(self) -> None:
        coverage_signals = [UnifiedSignal("coverage", 0.8, 0.30, "test")]
        evidence_signals = [UnifiedSignal("evidence", 0.7, 0.25, "test")]
        ats_signals = [UnifiedSignal("ats", 0.9, 0.20, "test")]
        interview_signals = []

        quality_signal = SignalMigrationAdapters.create_quality_signal(
            coverage_signals, evidence_signals, ats_signals, interview_signals
        )

        assert quality_signal.signal_type == "quality"
        assert quality_signal.score == 0.8  # (0.8 + 0.7 + 0.9) / 3
        assert quality_signal.weight == 0.10