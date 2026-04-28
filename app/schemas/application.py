# app\schemas\application.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApplicationCreateRequest(BaseModel):
    vacancy_id: UUID
    resume_document_id: UUID | None = None
    cover_letter_document_id: UUID | None = None
    notes: str | None = None


class ApplicationStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: UUID
    resume_document_id: UUID | None
    cover_letter_document_id: UUID | None
    status: str
    channel: str | None
    applied_at: datetime | None
    outcome: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationListItem(BaseModel):
    id: UUID
    vacancy_id: UUID
    vacancy_title: str | None = None
    vacancy_company: str | None = None
    vacancy_location: str | None = None
    resume_document_id: UUID | None
    cover_letter_document_id: UUID | None
    status: str
    channel: str | None
    applied_at: datetime | None
    outcome: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
