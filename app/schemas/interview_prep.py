# app\schemas\interview_prep.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class InterviewPrepSessionCreateRequest(StrictBaseModel):
    application_id: UUID


class InterviewPrepEvidenceLinkRead(StrictBaseModel):
    question_id: str
    question_category: str
    achievement_id: UUID
    achievement_title: str
    score: float
    reason: str


class InterviewPrepWeakAreaRead(StrictBaseModel):
    code: str
    message: str
    severity: str
    category: str | None = None
    competency_key: str | None = None
    evidence_count: int | None = None


class InterviewPrepReadinessRead(StrictBaseModel):
    ready: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    score: int | None = None


class InterviewPrepQuestionRead(StrictBaseModel):
    question_id: str
    category: str
    prompt: str
    answer_format: str
    competency_key: str | None = None
    competency_name: str | None = None
    recommended_evidence_ids: list[UUID] = Field(default_factory=list)
    recommended_evidence: list[dict[str, Any]] = Field(default_factory=list)


class InterviewPrepSessionRead(StrictBaseModel):
    id: UUID
    application_id: UUID
    vacancy_id: UUID
    prep_status: str
    readiness_score: int | None = None
    competency_map: dict[str, Any] = Field(default_factory=dict)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)
    weak_areas: list[dict[str, Any]] = Field(default_factory=list)
    readiness: InterviewPrepReadinessRead
    created_at: datetime
    updated_at: datetime


class InterviewPrepSessionListItem(StrictBaseModel):
    id: UUID
    application_id: UUID
    vacancy_id: UUID
    prep_status: str
    readiness_score: int | None = None
    created_at: datetime
    updated_at: datetime
