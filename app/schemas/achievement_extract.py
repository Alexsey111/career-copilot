# app\schemas\achievement_extract.py

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class AchievementExtractRequest(BaseModel):
    extraction_id: UUID


class AchievementItemRead(BaseModel):
    title: str
    fact_status: str


class AchievementExtractResponse(BaseModel):
    profile_id: UUID
    extraction_id: UUID
    achievement_count: int
    achievements: list[AchievementItemRead]
    warnings: list[str]