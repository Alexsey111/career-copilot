from app.services.signal_normalizer import (
    SignalNormalizer,
    normalize_coverage_score,
    normalize_evidence_score,
    normalize_interview_score,
    SIGNAL_USABLE_THRESHOLD,
    SIGNAL_ACCEPTABLE_THRESHOLD,
    SIGNAL_STRONG_THRESHOLD,
    SIGNAL_EXCELLENT_THRESHOLD,
)


class TestSignalNormalizer:
    """Тесты для нормализации scoring systems."""

    def test_normalize_to_standard_basic(self) -> None:
        """Базовая нормализация к 0.0-1.0."""
        assert SignalNormalizer.normalize_to_standard(50, 0, 100) == 0.5
        assert SignalNormalizer.normalize_to_standard(75, 0, 100) == 0.75
        assert SignalNormalizer.normalize_to_standard(0, 0, 100) == 0.0
        assert SignalNormalizer.normalize_to_standard(100, 0, 100) == 1.0

    def test_normalize_to_standard_clamps(self) -> None:
        """Нормализация clamp к диапазону."""
        assert SignalNormalizer.normalize_to_standard(-10, 0, 100) == 0.0
        assert SignalNormalizer.normalize_to_standard(150, 0, 100) == 1.0

    def test_normalize_percentage(self) -> None:
        """Нормализация процентов."""
        assert SignalNormalizer.normalize_percentage(85) == 0.85
        assert SignalNormalizer.normalize_percentage(0) == 0.0
        assert SignalNormalizer.normalize_percentage(100) == 1.0

    def test_get_quality_label(self) -> None:
        """Метки качества."""
        assert SignalNormalizer.get_quality_label(0.95) == "excellent"
        assert SignalNormalizer.get_quality_label(0.8) == "strong"
        assert SignalNormalizer.get_quality_label(0.6) == "acceptable"
        assert SignalNormalizer.get_quality_label(0.4) == "weak"
        assert SignalNormalizer.get_quality_label(0.2) == "unusable"
        assert SignalNormalizer.get_quality_label(0.0) == "unusable"

    def test_is_acceptable(self) -> None:
        """Проверка на приемлемость."""
        assert SignalNormalizer.is_acceptable(0.5) is True
        assert SignalNormalizer.is_acceptable(0.7) is True
        assert SignalNormalizer.is_acceptable(0.49) is False
        assert SignalNormalizer.is_acceptable(0.3) is False

    def test_is_strong(self) -> None:
        """Проверка на strong."""
        assert SignalNormalizer.is_strong(0.7) is True
        assert SignalNormalizer.is_strong(0.85) is True
        assert SignalNormalizer.is_strong(0.69) is False

    def test_scale_to_range(self) -> None:
        """Масштабирование к диапазону."""
        assert SignalNormalizer.scale_to_range(0.5, 0, 100) == 50.0
        assert SignalNormalizer.scale_to_range(0.75, 0, 100) == 75.0
        assert SignalNormalizer.scale_to_range(0.5, 50, 150) == 100.0


class TestNormalizationFunctions:
    """Тесты для функций нормализации."""

    def test_normalize_coverage_score(self) -> None:
        """Нормализация ATS match score."""
        assert normalize_coverage_score(85) == 0.85
        assert normalize_coverage_score(50) == 0.5
        assert normalize_coverage_score(0) == 0.0

    def test_normalize_evidence_score(self) -> None:
        """Нормализация evidence score."""
        assert normalize_evidence_score(0.8) == 0.8
        assert normalize_evidence_score(0.5) == 0.5
        assert normalize_evidence_score(1.5) == 1.0  # clamp
        assert normalize_evidence_score(-0.2) == 0.0  # clamp

    def test_normalize_interview_score(self) -> None:
        """Нормализация interview score."""
        assert normalize_interview_score(0.75) == 0.75
        assert normalize_interview_score(0.3) == 0.3


class TestThresholdConstants:
    """Тесты для пороговых значений."""

    def test_threshold_values(self) -> None:
        """Проверка констант порогов."""
        assert SIGNAL_USABLE_THRESHOLD == 0.3
        assert SIGNAL_ACCEPTABLE_THRESHOLD == 0.5
        assert SIGNAL_STRONG_THRESHOLD == 0.7
        assert SIGNAL_EXCELLENT_THRESHOLD == 0.9
