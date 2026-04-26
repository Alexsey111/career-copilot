# app\schemas\vacancy.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, model_validator


class VacancyImportRequest(BaseModel):
    source: str = "manual"
    source_url: str | None = None
    external_id: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description_raw: str | None = None

    @model_validator(mode="after")
    def validate_source_payload(self) -> "VacancyImportRequest":
        if not self.description_raw and not self.source_url:
            raise ValueError("either description_raw or source_url must be provided")
        return self


class VacancyImportResponse(BaseModel):
    # Keep both for now:
    # - id is the consistent public API name
    # - vacancy_id preserves backward compatibility with the current smoke flow
    id: UUID
    vacancy_id: UUID
    source: str
    source_url: str | None
    title: str
    company: str | None
    location: str | None
    description_length: int
    created_at: datetime


class VacancyRead(BaseModel):
    id: UUID
    source: str
    source_url: str | None
    external_id: str | None
    title: str
    company: str | None
    location: str | None
    description_raw: str
    description_length: int
    created_at: datetime
    updated_at: datetime


class VacancyAnalysisResponse(BaseModel):
    analysis_id: UUID
    vacancy_id: UUID
    must_have: list[dict[str, Any]]
    nice_to_have: list[dict[str, Any]]
    keywords: list[str]
    strengths: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    match_score: int | None
    analysis_version: str
    created_at: datetime