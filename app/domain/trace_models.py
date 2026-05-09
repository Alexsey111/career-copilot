# app/domain/trace_models.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GenerationTrace:
    """Трассировка генерации документа для explainability и debugging."""
    selected_achievement_ids: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    builder_version: str = "v1"
    renderer_version: str = "v1"
    prompt_version: str | None = None
    vacancy_analysis_id: str | None = None
    profile_extraction_id: str | None = None


@dataclass(slots=True)
class AIAuditMetadata:
    """Метаданные для AI enhancement operations."""
    model: str
    prompt_version: str
    temperature: float
    safety_checks_passed: bool = True
    tokens_used: dict[str, int] | None = None
    duration_ms: int | None = None
    provider: str | None = None


@dataclass(slots=True)
class DeterministicCheckResult:
    """Результат детерминированной валидации."""
    passed: bool
    check_name: str
    message: str
    severity: str = "warning"  # info, warning, critical


@dataclass(slots=True)
class DocumentEvaluationReport:
    """Отчёт о детерминированной оценке документа."""
    checks: list[DeterministicCheckResult] = field(default_factory=list)
    trace: GenerationTrace | None = None
    ai_metadata: AIAuditMetadata | None = None

    @property
    def is_safe(self) -> bool:
        """Возвращает True если нет критических проблем."""
        return all(
            check.severity != "critical" or check.passed
            for check in self.checks
        )

    @property
    def has_hallucinated_metrics(self) -> bool:
        """Проверка на выдуманные метрики."""
        return any(
            not check.passed and "hallucinated" in check.message.lower()
            for check in self.checks
        )

    @property
    def has_keyword_loss(self) -> bool:
        """Проверка на потерю ключевых слов."""
        return any(
            not check.passed and "keyword" in check.message.lower()
            for check in self.checks
        )
