# app\schemas\application.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreateRequest(BaseModel):
    vacancy_id: UUID
    resume_document_id: UUID | None = None
    cover_letter_document_id: UUID | None = None
    source: str | None = None
    notes: str | None = None


class ApplicationSubmitRequest(BaseModel):
    source: str | None = None
    external_link: str | None = None


class ApplicationStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class ApplicationWorkflowTransitionItem(BaseModel):
    status: str
    label: str


class ApplicationWorkflowResponse(BaseModel):
    current_status: str
    allowed_transitions: list[ApplicationWorkflowTransitionItem] = Field(default_factory=list)
    can_submit: bool = False
    is_final: bool = False
    review_required: bool = False
    review_blockers: list[str] = Field(default_factory=list)
    review_warnings: list[str] = Field(default_factory=list)


class ApplicationAnalyticsSummaryResponse(BaseModel):
    total_applications: int
    count_by_status: dict[str, int]
    created_per_day: dict[str, int]
    applied_per_day: dict[str, int]
    conversion_to_applied: float
    offers_count: int
    rejections_count: int
    average_time_to_apply_hours: float | None


class ApplicationReminderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: UUID
    reminder_type: str
    title: str
    description: str
    days_since_event: int


class ApplicationStatusHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    previous_status: str | None
    new_status: str
    notes: str | None
    changed_at: datetime


class ApplicationEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    title: str | None
    description: str | None
    meta_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class ApplicationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
    resume_document_id: UUID | None
    cover_letter_document_id: UUID | None
    status: str
    source: str | None
    external_link: str | None
    applied_at: datetime | None
    outcome: str | None
    notes: str | None
    review_required: bool = False
    review_blockers: list[str] = Field(default_factory=list)
    review_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ApplicationDashboardItem(BaseModel):
    id: UUID
    vacancy_id: UUID
    vacancy_title: str | None = None
    vacancy_company: str | None = None
    vacancy_location: str | None = None
    resume_document_id: UUID | None
    cover_letter_document_id: UUID | None
    status: str
    source: str | None
    external_link: str | None
    applied_at: datetime | None
    outcome: str | None
    notes: str | None
    review_required: bool = False
    review_blockers: list[str] = Field(default_factory=list)
    review_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# Backward-compatible aliases for the older response names.
ApplicationRead = ApplicationDetailResponse
ApplicationListItem = ApplicationDashboardItem
