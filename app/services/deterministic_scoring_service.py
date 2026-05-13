# app/services/deterministic_scoring_service.py

"""DeterministicScoringService — детерминированный расчет readiness scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.readiness_models import ReadinessScore, ReadinessSignal, RecommendationItem, RecommendationCategory


@dataclass(slots=True)
class ExtractedReadinessFeatures:
    """Extracted features для deterministic scoring."""
    # ATS features
    keyword_coverage: float = 0.0  # 0.0-1.0
    formatting_score: float = 0.0  # 0.0-1.0
    section_completeness: float = 0.0  # 0.0-1.0

    # Evidence features
    evidence_quality_avg: float = 0.0  # 0.0-1.0
    evidence_count: int = 0

    # Coverage features
    coverage_strength: float = 0.0  # 0.0-1.0
    requirements_covered: int = 0
    total_requirements: int = 0

    # Interview features
    interview_quality_score: float = 0.0  # 0.0-1.0

    # Quality features
    content_quality_score: float = 0.0  # 0.0-1.0


class DeterministicScoringService:
    """
    Детерминированный сервис расчета readiness scores.

    Все расчеты основаны на фиксированных правилах и весах.
    LLM отвечает только за extraction features, не за scoring.
    """

    # Фиксированные веса для компонентов
    COMPONENT_WEIGHTS = {
        "coverage": 0.30,
        "evidence": 0.25,
        "ats": 0.20,
        "interview": 0.15,
        "quality": 0.10,
    }

    # Веса внутри ATS компонента
    ATS_WEIGHTS = {
        "keyword_coverage": 0.5,
        "formatting": 0.2,
        "section_completeness": 0.3,
    }

    # Пороги для evidence quality
    EVIDENCE_THRESHOLDS = {
        "excellent": 0.8,
        "good": 0.6,
        "poor": 0.4,
    }

    def calculate_readiness(self, features: ExtractedReadinessFeatures) -> ReadinessScore:
        """
        Детерминированный расчет readiness score.

        Args:
            features: Extracted features от LLM или других источников

        Returns:
            ReadinessScore с детерминированными расчетами
        """
        # Рассчитываем компонентные scores
        ats_score = self._calculate_ats_score(features)
        evidence_score = self._calculate_evidence_score(features)
        coverage_score = self._calculate_coverage_score(features)
        interview_score = self._calculate_interview_score(features)
        quality_score = self._calculate_quality_score(features)

        # Рассчитываем overall score
        overall_score = self._calculate_overall_score({
            "ats": ats_score,
            "evidence": evidence_score,
            "coverage": coverage_score,
            "interview": interview_score,
            "quality": quality_score,
        })

        # Генерируем сигналы для прозрачности
        signals = self._create_signals(features, {
            "ats": ats_score,
            "evidence": evidence_score,
            "coverage": coverage_score,
            "interview": interview_score,
            "quality": quality_score,
        })

        # Определяем blocking issues и warnings
        blocking_issues = self._identify_blocking_issues(features)
        warnings = self._identify_warnings(features)

        # Генерируем рекомендации
        recommendations = self._generate_recommendations(overall_score, blocking_issues, warnings)

        return ReadinessScore(
            overall_score=overall_score,
            ats_score=ats_score,
            evidence_score=evidence_score,
            coverage_score=coverage_score,
            interview_score=interview_score,
            quality_score=quality_score,
            blocking_issues=blocking_issues,
            warnings=warnings,
            recommendations=recommendations,
        )

    def _calculate_ats_score(self, features: ExtractedReadinessFeatures) -> float:
        """Детерминированный расчет ATS score."""
        return (
            features.keyword_coverage * self.ATS_WEIGHTS["keyword_coverage"] +
            features.formatting_score * self.ATS_WEIGHTS["formatting"] +
            features.section_completeness * self.ATS_WEIGHTS["section_completeness"]
        )

    def _calculate_evidence_score(self, features: ExtractedReadinessFeatures) -> float:
        """Детерминированный расчет evidence score."""
        if features.evidence_count == 0:
            return 0.0

        # Базовый score от качества
        base_score = features.evidence_quality_avg

        # Бонус за количество доказательств (до 1.0)
        count_bonus = min(features.evidence_count / 5.0, 1.0) * 0.2

        return min(base_score + count_bonus, 1.0)

    def _calculate_coverage_score(self, features: ExtractedReadinessFeatures) -> float:
        """Детерминированный расчет coverage score."""
        if features.total_requirements == 0:
            return 0.0

        coverage_ratio = features.requirements_covered / features.total_requirements
        return features.coverage_strength * coverage_ratio

    def _calculate_interview_score(self, features: ExtractedReadinessFeatures) -> float:
        """Детерминированный расчет interview score."""
        return features.interview_quality_score

    def _calculate_quality_score(self, features: ExtractedReadinessFeatures) -> float:
        """Детерминированный расчет quality score."""
        return features.content_quality_score

    def _calculate_overall_score(self, component_scores: dict[str, float]) -> float:
        """Рассчитывает итоговый score с весами."""
        weighted_sum = 0.0
        total_weight = 0.0

        for component, weight in self.COMPONENT_WEIGHTS.items():
            score = component_scores.get(component, 0.0)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _create_signals(
        self,
        features: ExtractedReadinessFeatures,
        component_scores: dict[str, float]
    ) -> list[ReadinessSignal]:
        """Создает сигналы для прозрачности расчетов."""
        signals = []

        signals.append(ReadinessSignal(
            signal_type="ats",
            score=component_scores["ats"],
            weight=self.COMPONENT_WEIGHTS["ats"],
            source="deterministic_calculation",
            metadata={
                "keyword_coverage": features.keyword_coverage,
                "formatting_score": features.formatting_score,
                "section_completeness": features.section_completeness,
            }
        ))

        signals.append(ReadinessSignal(
            signal_type="evidence",
            score=component_scores["evidence"],
            weight=self.COMPONENT_WEIGHTS["evidence"],
            source="deterministic_calculation",
            metadata={
                "evidence_quality_avg": features.evidence_quality_avg,
                "evidence_count": features.evidence_count,
            }
        ))

        signals.append(ReadinessSignal(
            signal_type="coverage",
            score=component_scores["coverage"],
            weight=self.COMPONENT_WEIGHTS["coverage"],
            source="deterministic_calculation",
            metadata={
                "coverage_strength": features.coverage_strength,
                "requirements_covered": features.requirements_covered,
                "total_requirements": features.total_requirements,
            }
        ))

        return signals

    def _identify_blocking_issues(self, features: ExtractedReadinessFeatures) -> list[str]:
        """Идентифицирует blocking issues."""
        issues = []

        if features.keyword_coverage < 0.3:
            issues.append("Критически низкое покрытие ключевых слов")

        if features.evidence_quality_avg < 0.4:
            issues.append("Недостаточное качество доказательств")

        if features.coverage_strength < 0.5:
            issues.append("Слабое покрытие требований вакансии")

        return issues

    def _identify_warnings(self, features: ExtractedReadinessFeatures) -> list[str]:
        """Идентифицирует warnings."""
        warnings = []

        if features.formatting_score < 0.7:
            warnings.append("Проблемы с форматированием для ATS")

        if features.section_completeness < 0.8:
            warnings.append("Неполные разделы резюме")

        if features.evidence_count < 3:
            warnings.append("Мало доказательств достижений")

        return warnings

    def _generate_recommendations(
        self,
        overall_score: float,
        blocking_issues: list[str],
        warnings: list[str]
    ) -> list[RecommendationItem]:
        """Генерирует рекомендации на основе scores."""
        recommendations = []

        if overall_score < 0.5:
            recommendations.append(RecommendationItem(
                message="Критически низкая готовность резюме",
                category=RecommendationCategory.GENERAL,
                severity="error"
            ))

        for issue in blocking_issues:
            recommendations.append(RecommendationItem(
                message=f"Исправить: {issue}",
                category=RecommendationCategory.GENERAL,
                severity="error"
            ))

        for warning in warnings:
            recommendations.append(RecommendationItem(
                message=f"Улучшить: {warning}",
                category=RecommendationCategory.GENERAL,
                severity="warning"
            ))

        return recommendations