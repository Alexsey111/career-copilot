# app\schemas\achievement_extract.py

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.json_contracts import FactStatus, StrictBaseModel


class AchievementExtractRequest(StrictBaseModel):
    extraction_id: UUID


class AchievementItemRead(StrictBaseModel):
    id: UUID
    title: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = None
    fact_status: FactStatus
    evidence_note: str | None = None


class AchievementExtractResponse(StrictBaseModel):
    profile_id: UUID
    extraction_id: UUID
    achievement_count: int
    achievements: list[AchievementItemRead]
    warnings: list[str]


class AchievementReviewRequest(StrictBaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = Field(default=None, max_length=255)
    fact_status: Literal["needs_confirmation", "confirmed"] = "confirmed"
    evidence_note: str | None = None


class AchievementReviewResponse(StrictBaseModel):
    id: UUID
    title: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = None
    fact_status: FactStatus
    evidence_note: str | None = None
    updated_at: datetime
