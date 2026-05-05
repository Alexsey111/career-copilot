# app\schemas\document.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResumeGenerateRequest(BaseModel):
    vacancy_id: UUID


class DocumentVersionRead(BaseModel):
    id: UUID
    vacancy_id: UUID | None
    document_kind: str
    version_label: str | None
    review_status: str
    is_active: bool
    rendered_text: str | None
    created_at: datetime
    updated_at: datetime


class ResumeGenerateResponse(BaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    rendered_text_preview: str


class CoverLetterGenerateRequest(BaseModel):
    vacancy_id: UUID


class CoverLetterGenerateResponse(BaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    rendered_text_preview: str


class DocumentReviewRequest(BaseModel):
    review_status: str
    review_comment: str | None = None
    set_active_when_approved: bool = True


class DocumentReviewResponse(BaseModel):
    document_id: UUID
    document_kind: str
    review_status: str
    is_active: bool
    review_comment: str | None
    updated_at: datetime


class ResumeEnhanceRequest(BaseModel):
    resume_text: str


class ResumeEnhanceResponse(BaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    enhanced_text: str
