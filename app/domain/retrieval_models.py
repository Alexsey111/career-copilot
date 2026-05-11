from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievalDecision:
    """Решение о retrieval достижений для требования."""
    requirement_id: str
    requirement_text: str
    retrieved_achievement_ids: list[str]
    retrieval_scores: dict[str, float]  # achievement_id -> score
    retrieval_method: str  # keyword_match | semantic | hybrid
    threshold_used: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Проверяет, что ничего не найдено."""
        return len(self.retrieved_achievement_ids) == 0

    @property
    def top_achievement_id(self) -> str | None:
        """ID лучшего достижения."""
        if not self.retrieved_achievement_ids:
            return None
        return max(
            self.retrieved_achievement_ids,
            key=lambda aid: self.retrieval_scores.get(aid, 0.0)
        )


@dataclass(slots=True)
class RetrievalTrace:
    """Трассировка процесса retrieval."""
    decisions: list[RetrievalDecision] = field(default_factory=list)
    total_achievements_available: int = 0
    total_achievements_retrieved: int = 0
    average_retrieval_score: float = 0.0

    @property
    def coverage_rate(self) -> float:
        """Процент требований с найденными достижениями."""
        if not self.decisions:
            return 0.0
        covered = sum(1 for d in self.decisions if not d.is_empty)
        return round(covered / len(self.decisions), 3)
