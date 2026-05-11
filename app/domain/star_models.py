from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.constants import EvidenceStrength, Priority, CoverageType


@dataclass(slots=True)
class STARStoryDraft:
    """Структурированная STAR-история из достижения."""
    achievement_id: str
    situation: str
    task: str
    action: str
    result: str
    evidence_strength: EvidenceStrength | str
    quality_score: float = 0.0

    @property
    def is_complete(self) -> bool:
        """Проверяет полноту STAR-компонентов."""
        return bool(
            self.situation.strip()
            and self.task.strip()
            and self.action.strip()
            and self.result.strip()
        )

    @property
    def summary(self) -> str:
        """Краткое резюме истории."""
        return f"{self.action} → {self.result}"


@dataclass(slots=True)
class Competency:
    """Компетенция из вакансии."""
    name: str
    description: str | None = None
    keywords: list[str] = field(default_factory=list)
    priority: Priority | str = Priority.IMPORTANT


@dataclass(slots=True)
class CompetencyMapping:
    """Маппинг требования → компетенция → STAR истории."""
    requirement_text: str
    competency: Competency
    matched_story_ids: list[str] = field(default_factory=list)
    coverage_type: CoverageType | str = CoverageType.UNSUPPORTED
    coverage_strength: float = 0.0
