from __future__ import annotations

from app.domain.constants import (
    SIGNAL_USABLE_THRESHOLD,
    SIGNAL_ACCEPTABLE_THRESHOLD,
    SIGNAL_STRONG_THRESHOLD,
    SIGNAL_EXCELLENT_THRESHOLD,
)


class SignalNormalizer:
    """
    Нормализация scoring systems к единой шкале 0.0 - 1.0.

    Стандартные пороги:
    - 0.0: unusable — данные непригодны
    - 0.3: weak — минимальный порог приемлемости
    - 0.5: acceptable — удовлетворительное качество
    - 0.7: strong — хорошее качество
    - 0.9: excellent — отличное качество
    """

    @staticmethod
    def normalize_to_standard(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """
        Нормализует score к стандартной шкале 0.0 - 1.0.

        Args:
            score: Исходный score
            min_val: Минимальное значение в исходной шкале
            max_val: Максимальное значение в исходной шкале

        Returns:
            Нормализованный score в диапазоне [0.0, 1.0]
        """
        if max_val == min_val:
            return 0.0

        normalized = (score - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, round(normalized, 3)))

    @staticmethod
    def normalize_percentage(score: float) -> float:
        """Нормализует процент (0-100) к шкале 0.0-1.0."""
        return SignalNormalizer.normalize_to_standard(score, min_val=0.0, max_val=100.0)

    @staticmethod
    def get_quality_label(score: float) -> str:
        """
        Возвращает текстовую метку качества для нормализованного score.

        Args:
            score: Нормализованный score (0.0 - 1.0)

        Returns:
            Метка: unusable | weak | acceptable | strong | excellent
        """
        if score >= SIGNAL_EXCELLENT_THRESHOLD:
            return "excellent"
        if score >= SIGNAL_STRONG_THRESHOLD:
            return "strong"
        if score >= SIGNAL_ACCEPTABLE_THRESHOLD:
            return "acceptable"
        if score >= SIGNAL_USABLE_THRESHOLD:
            return "weak"
        return "unusable"

    @staticmethod
    def is_acceptable(score: float) -> bool:
        """Проверяет, что score >= ACCEPTABLE_THRESHOLD (0.5)."""
        return score >= SIGNAL_ACCEPTABLE_THRESHOLD

    @staticmethod
    def is_strong(score: float) -> bool:
        """Проверяет, что score >= STRONG_THRESHOLD (0.7)."""
        return score >= SIGNAL_STRONG_THRESHOLD

    @staticmethod
    def scale_to_range(score: float, new_min: float, new_max: float) -> float:
        """
        Масштабирует нормализованный score (0.0-1.0) к новому диапазону.

        Args:
            score: Нормализованный score
            new_min: Новая минимальная граница
            new_max: Новая максимальная граница

        Returns:
            Score в новом диапазоне
        """
        if new_max == new_min:
            return new_min

        scaled = score * (new_max - new_min) + new_min
        return round(scaled, 3)


def normalize_coverage_score(raw_score: float) -> float:
    """Нормализует score покрытия (ATS match score из 100)."""
    return SignalNormalizer.normalize_percentage(raw_score)


def normalize_evidence_score(raw_score: float) -> float:
    """Нормализует score качества доказательств (уже 0.0-1.0)."""
    return min(1.0, max(0.0, round(raw_score, 3)))


def normalize_interview_score(raw_score: float) -> float:
    """Нормализует score интервью (уже 0.0-1.0)."""
    return min(1.0, max(0.0, round(raw_score, 3)))
