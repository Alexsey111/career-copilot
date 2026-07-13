# app\schemas\case_prep.py

"""Pydantic-схема ответа ``GET /interview-prep/cases/{vacancy_id}`` (Этап 9.E).

enum-поля (``case_type``, ``framework``, ``match_confidence``, ``match_type``,
``source_type``, ``fact_status``) — ``str`` без Literal: домен может
эволюционировать, стабильные категории описаны в
``docs/interview_prep_contract.md`` (Stable Case Types).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class CaseProvenanceResponse(StrictBaseModel):
    sources: list[str] = Field(default_factory=list)
    requires_human_review: bool = True
    notes: list[str] = Field(default_factory=list)


class RecommendedEvidenceResponse(StrictBaseModel):
    achievement_id: UUID | None = None
    title: str
    score: float | None = None
    reason: str
    source_type: str
    fact_status: str
    skills: list[str] = Field(default_factory=list)
    match_confidence: str
    match_type: str


class PracticeCaseResponse(StrictBaseModel):
    case_id: str
    case_type: str
    title: str
    prompt: str
    framework: str
    time_guidance: str
    rubric: list[str] = Field(default_factory=list)
    suggested_approach: list[str] = Field(default_factory=list)
    recommended_evidence: list[RecommendedEvidenceResponse] = Field(default_factory=list)
    competency_key: str | None = None
    source_requirement: str | None = None
    gap_severity: str | None = None
    provenance: CaseProvenanceResponse


class CasePrepReportResponse(StrictBaseModel):
    vacancy_id: UUID
    cases: list[PracticeCaseResponse] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    provenance: CaseProvenanceResponse