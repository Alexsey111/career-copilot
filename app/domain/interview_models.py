# app/domain/interview_models.py

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class InterviewQuestionDraft:
    """Typed draft для генерации вопросов интервью."""
    type: str
    source: str
    prompt: str
    answer_format: str
    rubric: list[str]
    keyword: str | None = None
    requirement_text: str | None = None
    achievement_title: str | None = None
    fact_status: str | None = None


@dataclass(slots=True)
class InterviewFeedbackDraft:
    """Typed draft для генерации фидбека."""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    coaching: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InterviewScoreDraft:
    """Typed draft для scoring."""
    overall: float | None = None
    by_category: dict[str, float] = field(default_factory=dict)
    readiness_score: int | None = None
