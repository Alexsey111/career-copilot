# app\schemas\health.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class HealthCountsResponse(StrictBaseModel):
    vacancies: int = 0
    applications: int = 0
    documents: int = 0
    interview_sessions: int = 0


class HealthApplicationSummary(StrictBaseModel):
    id: UUID
    vacancy_id: UUID
    status: str
    source: str | None = None
    resume_document_id: UUID | None = None
    cover_letter_document_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class HealthDocumentSummary(StrictBaseModel):
    id: UUID
    vacancy_id: UUID | None = None
    document_kind: str
    version_label: str | None = None
    review_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HealthDiagnosticsResponse(StrictBaseModel):
    status: str = "ok"
    backend_reachable: bool = True
    db_reachable: bool = True
    current_user_id: UUID | None = None
    counts: HealthCountsResponse = Field(default_factory=HealthCountsResponse)
    current_active_application: HealthApplicationSummary | None = None
    active_documents: dict[str, HealthDocumentSummary | None] = Field(default_factory=dict)
    demo_state: dict[str, Any] = Field(default_factory=dict)
    scenario_identifiers: list[dict[str, str]] = Field(default_factory=list)
