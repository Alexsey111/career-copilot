# app\schemas\vacancy.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.json_contracts import StrictBaseModel


class VacancyImportRequest(StrictBaseModel):
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


class VacancyImportFromUrlRequest(StrictBaseModel):
    source_url: str = Field(min_length=1)


class VacancyImportFromFileRequest(StrictBaseModel):
    source_file_id: UUID
    title: str | None = None
    company: str | None = None
    location: str | None = None
    source_url: str | None = None


class VacancyImportResponse(StrictBaseModel):
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


class VacancyRead(StrictBaseModel):
    id: UUID
    source: str
    source_url: str | None
    external_id: str | None
    title: str
    company: str | None
    location: str | None
    salary_from: int | None
    salary_to: int | None
    salary_currency: str | None
    employment_type: str | None
    experience_level: str | None
    published_at: datetime | None
    description_raw: str
    description_length: int
    created_at: datetime
    updated_at: datetime


class VacancyAnalysisResponse(StrictBaseModel):
    analysis_id: UUID
    vacancy_id: UUID
    must_have: list[dict[str, Any]]
    nice_to_have: list[dict[str, Any]]
    keywords: list[str]
    strengths: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    risks: list[dict[str, Any]] = Field(default_factory=list)
    match_logic: dict[str, Any] = Field(default_factory=dict)
    language_tone_hints: dict[str, Any] = Field(default_factory=dict)
    match_score: int | None
    analysis_version: str
    created_at: datetime


class VacancyFitEvidenceRead(StrictBaseModel):
    evidence_id: UUID | None = None
    title: str
    reason: str
    score: float | None = None
    fact_status: str | None = None
    evidence_strength: str | None = None
    star_preview: dict[str, Any] = Field(default_factory=dict)
    snippet_text: str | None = None


class VacancyFitRequirementRead(StrictBaseModel):
    requirement: str
    scope: str
    severity: str
    coverage_level: str
    reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    supporting_evidence: list[VacancyFitEvidenceRead] = Field(default_factory=list)


class VacancyFitCoverageRead(StrictBaseModel):
    required: list[str] = Field(default_factory=list)
    strong: list[VacancyFitRequirementRead] = Field(default_factory=list)
    medium: list[VacancyFitRequirementRead] = Field(default_factory=list)
    missing: list[VacancyFitRequirementRead] = Field(default_factory=list)


class VacancyFitResponse(StrictBaseModel):
    analysis_id: UUID | None = None
    analysis_version: str | None = None
    vacancy_id: UUID
    overall_fit_score: int
    skills_fit: int
    evidence_fit: int
    experience_fit: int
    leadership_fit: int
    gap_severity: str
    readiness_recommendation: str
    requirements: list[VacancyFitRequirementRead] = Field(default_factory=list)
    evidence_coverage: VacancyFitCoverageRead


class VacancyMatchResponse(StrictBaseModel):
    vacancy_id: UUID
    user_id: UUID
    match_score: int | None
    strengths: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    message: str | None = None


class VacancySearchRequest(StrictBaseModel):
    query: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class VacancySearchItem(StrictBaseModel):
    id: UUID
    source: str
    source_url: str | None
    title: str
    company: str | None
    location: str | None
    salary_from: int | None
    salary_to: int | None
    salary_currency: str | None
    employment_type: str | None
    experience_level: str | None
    similarity: float | None = None
    created_at: datetime


class VacancySearchResponse(StrictBaseModel):
    items: list[VacancySearchItem]
    total: int
    limit: int
    offset: int
