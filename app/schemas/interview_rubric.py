# app\schemas\interview_rubric.py

"""Pydantic-схемы per-criterion rubric scoring ответов (Этап 9.F).

enum-поля (``case_type``, ``level``, ``grade``, ``trend``) — ``str`` без Literal:
стабильные категории описаны в ``docs/interview_prep_contract.md``
(Answer Rubric Scoring, Cross-Session Progress).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class AnswerSubmitRequest(StrictBaseModel):
    case_id: str = Field(min_length=1, max_length=64)
    case_type: str = Field(min_length=1, max_length=50)
    answer_text: str = Field(min_length=1)


class CriterionScoreResponse(StrictBaseModel):
    criterion: str
    score: int = Field(ge=0, le=3)
    level: str
    reason: str


class RubricFeedbackResponse(StrictBaseModel):
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class RubricScoreResponse(StrictBaseModel):
    attempt_id: UUID
    case_id: str
    case_type: str
    criterion_scores: list[CriterionScoreResponse] = Field(default_factory=list)
    overall_score: float = Field(ge=0, le=100)
    grade: str
    feedback: RubricFeedbackResponse
    rubric_version: str
    requires_human_review: bool = True
    created_at: datetime


class AnswerAttemptListItem(StrictBaseModel):
    attempt_id: UUID
    case_id: str
    case_type: str
    overall_score: float = Field(ge=0, le=100)
    grade: str
    created_at: datetime


class CriterionProgressResponse(StrictBaseModel):
    criterion: str
    first: int = Field(ge=0, le=3)
    last: int = Field(ge=0, le=3)
    best: int = Field(ge=0, le=3)
    improvement: int = Field(ge=-3, le=3)


class OverallProgressResponse(StrictBaseModel):
    first: float = Field(ge=0, le=100)
    last: float = Field(ge=0, le=100)
    best: float = Field(ge=0, le=100)
    improvement: float
    trend: str


class RubricProgressResponse(StrictBaseModel):
    vacancy_id: UUID
    case_id: str
    total_attempts: int = Field(ge=0)
    overall: OverallProgressResponse | None = None
    per_criterion: list[CriterionProgressResponse] = Field(default_factory=list)
    reason: str | None = None