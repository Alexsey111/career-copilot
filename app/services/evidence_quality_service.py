from __future__ import annotations

import re
from typing import Any

from app.domain.coverage_models import RequirementCoverage
from app.domain.constants import (
    GENERIC_PATTERNS,
    EVIDENCE_SCORE_EXCELLENT_THRESHOLD,
    EVIDENCE_SCORE_GOOD_THRESHOLD,
    EVIDENCE_SCORE_ACCEPTABLE_THRESHOLD,
    QualityLabel,
)

STRONG_SIGNALS = [
    r"\d+%",
    r"\d+\s*(users|customers|requests|tickets|issues)",
    r"\$\d+",
    r"\b(reduced|decreased|lowered)\b",
    r"\b(increased|improved|boosted|enhanced)\b",
    r"\boptimized\b",
    r"\blaunched\b",
    r"\bimplemented\b",
    r"\bdesigned\b",
    r"\barchitected\b",
    r"\bdelivered\b",
    r"\bcompleted\b",
]

SPECIFIC_ACTION_VERBS = [
    r"\bimplemented\b",
    r"\bdeveloped\b",
    r"\bdesigned\b",
    r"\barchitected\b",
    r"\bcreated\b",
    r"\bbuilt\b",
    r"\bengineered\b",
    r"\bdeployed\b",
    r"\bconfigured\b",
    r"\bautomated\b",
    r"\brestructured\b",
    r"\brefactored\b",
    r"\boptimized\b",
    r"\bintegrated\b",
    r"\bmigrated\b",
    r"\bsetup\b",
    r"\bconfigured\b",
]

TECHNICAL_SPECIFICITY_PATTERNS = [
    r"\b\w+\s*\+\s*\w+\b",  # tech stack like "Python + FastAPI"
    r"\b\d+\.?\d*\s*(kb|mb|gb|tb)\b",  # size metrics
    r"\b\d+\.?\d*\s*(ms|s|min|hr)\b",  # time metrics
    r"\b\w+api\b",  # API references
    r"\b\w+db\b",  # database references
    r"\bdocker\b",
    r"\bkubernetes\b",
    r"\baws\b",
    r"\bgcp\b",
    r"\bazure\b",
    r"\bkafka\b",
    r"\bredis\b",
    r"\bpostgres\b",
    r"\bmongodb\b",
    r"\belastic\b",
]


class EvidenceQualityService:
    """Сервис оценки качества доказательств в достижениях."""

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in re.findall(r"\w+", text.lower()) if token]

    @staticmethod
    def detect_generic_evidence(text: str) -> bool:
        """
        Проверяет, является ли текст achievement generic фразой.

        Возвращает True если найдены generic patterns.
        """
        text_lower = text.lower()
        for pattern in GENERIC_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    @staticmethod
    def count_strong_signals(text: str) -> int:
        """
        Считает количество strong signals в тексте.

        Strong signals: метрики, измеримые результаты, конкретные действия.
        """
        text_lower = text.lower()
        count = 0
        for pattern in STRONG_SIGNALS:
            if re.search(pattern, text_lower):
                count += 1
        return count

    @staticmethod
    def count_action_verbs(text: str) -> int:
        """
        Считает количество специфических action verbs.
        """
        text_lower = text.lower()
        count = 0
        for pattern in SPECIFIC_ACTION_VERBS:
            if re.search(pattern, text_lower):
                count += 1
        return count

    @staticmethod
    def count_technical_specificity(text: str) -> int:
        """
        Считает количество технических спецификаций.
        """
        text_lower = text.lower()
        count = 0
        for pattern in TECHNICAL_SPECIFICITY_PATTERNS:
            if re.search(pattern, text_lower):
                count += 1
        return count

    def calculate_evidence_quality_score(
        self,
        achievement: dict[str, Any],
    ) -> float:
        """
        Рассчитывает evidence_quality_score для одного достижения.

        Score от 0.0 до 1.0 на основе:
        - measurable metrics (0-0.3)
        - specific action verbs (0-0.25)
        - technical specificity (0-0.25)
        - evidence note present (0-0.1)
        - penalty for generic wording (-0-0.2)

        Returns: float от 0.0 до 1.0
        """
        achievement_text = " ".join(
            str(achievement.get(field) or "")
            for field in [
                "title",
                "situation",
                "task",
                "action",
                "result",
                "metric_text",
            ]
        )

        evidence_note = str(achievement.get("evidence_note") or "").strip()

        # Base score components
        signal_count = self.count_strong_signals(achievement_text)
        verb_count = self.count_action_verbs(achievement_text)
        tech_count = self.count_technical_specificity(achievement_text)
        has_evidence_note = bool(evidence_note)
        is_generic = self.detect_generic_evidence(achievement_text)

        # Calculate weighted components
        metric_score = min(signal_count * 0.1, 0.3)
        verb_score = min(verb_count * 0.08, 0.25)
        tech_score = min(tech_count * 0.08, 0.25)
        evidence_score = 0.1 if has_evidence_note else 0.0

        # Generic penalty
        generic_penalty = 0.2 if is_generic else 0.0

        # Final score
        raw_score = metric_score + verb_score + tech_score + evidence_score - generic_penalty

        return max(0.0, min(1.0, round(raw_score, 3)))

    def evaluate_evidence_quality(
        self,
        coverage: list[RequirementCoverage],
    ) -> list[tuple[RequirementCoverage, float]]:
        """
        Оценивает качество доказательств для всех покрытий.

        Возвращает список кортежей (coverage_item, quality_score).
        """
        results: list[tuple[RequirementCoverage, float]] = []

        # Нужно получить достижения по ID
        # В реальном коде здесь будет lookup
        for item in coverage:
            # Для MVP используем requirement_text как placeholder
            # В будущем нужно передавать сами достижения
            quality_score = self.calculate_evidence_quality_score({
                "title": item.requirement_text,
                "situation": "",
                "task": "",
                "action": "",
                "result": "",
                "metric_text": "",
                "evidence_note": item.evidence_summary or "",
            })
            results.append((item, quality_score))

        return results

    def get_quality_label(self, score: float) -> str:
        """
        Возвращает текстовую метку качества на основе score.
        """
        if score >= EVIDENCE_SCORE_EXCELLENT_THRESHOLD:
            return QualityLabel.EXCELLENT
        if score >= EVIDENCE_SCORE_GOOD_THRESHOLD:
            return QualityLabel.GOOD
        if score >= EVIDENCE_SCORE_ACCEPTABLE_THRESHOLD:
            return QualityLabel.ACCEPTABLE
        if score > 0.0:
            return QualityLabel.WEAK
        return QualityLabel.MISSING
