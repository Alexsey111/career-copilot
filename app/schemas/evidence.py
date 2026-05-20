# app\schemas\evidence.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class EvidenceSnippetItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    snippet_text: str
    source_type: str
    skills: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("skills", "skills_json"),
    )
    evidence_strength: str
    fact_status: str
    usage_count: int
    used_in_documents_count: int
    used_in_interviews_count: int
    star_summary: dict = Field(
        default_factory=dict,
        validation_alias=AliasChoices("star_summary", "star_summary_json"),
    )
    created_at: datetime
    updated_at: datetime


class EvidenceUsageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_snippet_id: UUID
    usage_type: str
    target_type: str | None
    target_id: str | None
    note: str | None
    created_at: datetime


class EvidenceInsightsRecommendationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    evidence_id: UUID | None
    title: str
    message: str
    severity: str


class EvidenceInsightsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weak_evidence_count: int
    missing_metrics_count: int
    missing_star_fields_count: int
    unused_evidence_count: int
    overused_evidence_count: int
    unverified_evidence_count: int
    recommendations: list[EvidenceInsightsRecommendationItem]
