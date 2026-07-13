# app\schemas\career_strategy.py

"""Pydantic-схема ответа ``GET /target-tracks/{id}/strategy`` (Этап 9.D).

enum-поля (``step_type``, ``priority``, ``severity``, ``confidence``,
``estimated_effort``, ``channel_type``) — ``str`` без Literal: домен может
эволюционировать, а контракты стабильности категорий описаны в
``docs/career_strategy.md`` (по образцу ``CareerInsightRecommendationItem.priority``
в ``app/schemas/career_insights.py``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class GapSummaryItemResponse(StrictBaseModel):
    keyword: str
    count: int
    severity: str
    example_vacancy_titles: list[str] = Field(default_factory=list)
    is_relevant_to_track: bool
    relevance_reason: str | None = None


class LearningPlanStepResponse(StrictBaseModel):
    order: int
    gap_keyword: str
    step_type: str
    action: str
    rationale: str
    priority: str
    estimated_effort: str
    prerequisites: list[str] = Field(default_factory=list)


class LearningPlanResponse(StrictBaseModel):
    steps: list[LearningPlanStepResponse] = Field(default_factory=list)
    projected_coverage: dict[str, Any] = Field(default_factory=dict)


class SearchTacticResponse(StrictBaseModel):
    channel_type: str
    tactic: str
    rationale: str
    priority: str


class StrategyProvenanceResponse(StrictBaseModel):
    sources: list[str] = Field(default_factory=list)
    confidence: str
    requires_human_review: bool = True
    notes: list[str] = Field(default_factory=list)


class CareerStrategyResponse(StrictBaseModel):
    track_id: UUID
    gap_summary: list[GapSummaryItemResponse] = Field(default_factory=list)
    learning_plan: LearningPlanResponse
    search_tactics: list[SearchTacticResponse] = Field(default_factory=list)
    provenance: StrategyProvenanceResponse