from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class CareerInsightGapItem(StrictBaseModel):
    keyword: str
    count: int
    severity: str
    example_vacancy_titles: list[str] = Field(default_factory=list)


class CareerInsightEvidenceItem(StrictBaseModel):
    evidence_id: UUID | None = None
    title: str
    evidence_strength: str
    fact_status: str
    usage_count: int
    used_in_documents_count: int
    used_in_interviews_count: int
    reason: str | None = None


class CareerInsightApplicationPatternItem(StrictBaseModel):
    applications_sent: int
    interviews_reached: int
    offers_count: int
    most_common_rejection_stage: str | None = None
    most_common_rejection_stage_count: int = 0
    conversion_to_interview: float
    conversion_to_offer: float


class CareerInsightRecommendationItem(StrictBaseModel):
    code: str
    title: str
    message: str
    priority: str


class CareerInsightsResponse(StrictBaseModel):
    generated_at: datetime
    repeated_gaps: list[CareerInsightGapItem] = Field(default_factory=list)
    evidence_coverage_trends: dict[str, Any]
    application_patterns: CareerInsightApplicationPatternItem
    strategic_recommendations: list[CareerInsightRecommendationItem] = Field(default_factory=list)
    vacancy_intelligence_sample: list[dict[str, Any]] = Field(default_factory=list)
