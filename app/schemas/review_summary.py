# app/schemas/review_summary.py

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class ReviewSummaryResponse(StrictBaseModel):
    entity_type: Literal["document", "interview_prep"]
    entity_id: UUID
    ready: bool
    requires_human_review: bool = True
    risk_level: Literal["low", "medium", "high"]
    quality: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    claims_requiring_confirmation: list[dict[str, Any]] = Field(default_factory=list)
    gap_risk_items: list[dict[str, Any]] = Field(default_factory=list)
    selected_evidence: list[dict[str, Any]] = Field(default_factory=list)
    provenance_summary: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
