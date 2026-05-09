# app\schemas\document.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.json_contracts import DocumentKind, StrictBaseModel

class ResumeGenerateRequest(StrictBaseModel):
    vacancy_id: UUID


class DocumentVersionRead(StrictBaseModel):
    id: UUID
    vacancy_id: UUID | None
    analysis_id: UUID | None
    document_kind: DocumentKind
    version_label: str | None
    review_status: str
    is_active: bool
    rendered_text: str | None
    created_at: datetime
    updated_at: datetime


class ResumeGenerateResponse(StrictBaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    rendered_text_preview: str


class CoverLetterGenerateRequest(StrictBaseModel):
    vacancy_id: UUID


class CoverLetterGenerateResponse(StrictBaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    rendered_text_preview: str


class DocumentReviewRequest(StrictBaseModel):
    review_status: str
    review_comment: str | None = None
    set_active_when_approved: bool = True


class DocumentReviewResponse(StrictBaseModel):
    document_id: UUID
    document_kind: DocumentKind
    review_status: str
    is_active: bool
    review_comment: str | None
    updated_at: datetime


class ResumeEnhanceRequest(StrictBaseModel):
    resume_text: str


class ResumeEnhanceResponse(StrictBaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    enhanced_text: str


class CoverLetterEnhanceRequest(StrictBaseModel):
    cover_letter_text: str


class CoverLetterEnhanceResponse(StrictBaseModel):
    document_id: UUID
    vacancy_id: UUID
    review_status: str
    version_label: str | None
    created_at: datetime
    enhanced_text: str


class DocumentHistoryItem(StrictBaseModel):
    id: UUID
    derived_from_id: UUID | None
    version_label: str | None
    review_status: str
    is_active: bool
    created_at: datetime


class DocumentHistoryResponse(StrictBaseModel):
    items: list[DocumentHistoryItem]


class DocumentDiffResponse(StrictBaseModel):
    document_id: UUID
    other_document_id: UUID
    document_kind: DocumentKind
    diff: str


class DocumentActivateResponse(StrictBaseModel):
    document_id: UUID
    document_kind: DocumentKind
    is_active: bool
    activated_at: datetime


class DocumentRollbackResponse(StrictBaseModel):
    document_id: UUID
    source_document_id: UUID
    document_kind: DocumentKind
    is_active: bool
    created_at: datetime

class ActiveDocumentResponse(StrictBaseModel):
    id: UUID
    vacancy_id: UUID | None
    document_kind: DocumentKind
    version_label: str | None
    review_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    rendered_text: str | None
