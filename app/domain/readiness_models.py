from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.recommendation_models import RecommendationTask


@dataclass(slots=True)
class RecommendationItem:
    """Typed recommendation produced by the readiness scoring engine."""
    message: str
    category: str = ""
    severity: str = "info"


@dataclass(slots=True)
class ReadinessSignal:
    """Сигнал готовности из одного источника."""
    signal_type: str  # coverage | evidence | interview | ats | etc
    score: float  # 0.0 - 1.0
    weight: float  # вес сигнала в итоговой оценке
    source: str  # откуда получен сигнал
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReadinessScore:
    """Итоговая оценка готовности документа."""
    overall_score: float  # 0.0 - 1.0

    # Компонентные scores
    ats_score: float = 0.0
    evidence_score: float = 0.0
    interview_score: float = 0.0
    coverage_score: float = 0.0
    quality_score: float = 0.0

    # Проблемы
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Рекомендации
    recommendations: list[RecommendationItem] = field(default_factory=list)
    recommendation_tasks: list[RecommendationTask] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """Проверяет, готов ли документ."""
        return len(self.blocking_issues) == 0 and self.overall_score >= 0.7

    @property
    def readiness_level(self) -> str:
        """Уровень готовности."""
        if self.is_ready:
            return "ready"
        if self.overall_score >= 0.5:
            return "needs_work"
        return "not_ready"
