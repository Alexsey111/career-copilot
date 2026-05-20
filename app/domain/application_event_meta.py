from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from uuid import UUID


class ApplicationCreatedEventMeta(TypedDict):
    vacancy_id: str
    resume_document_id: str | None
    cover_letter_document_id: str | None


class ApplicationStatusChangedEventMeta(TypedDict):
    previous_status: str | None
    new_status: str
    source: str


class ApplicationAppliedEventMeta(TypedDict):
    source: str
    external_link: str | None
    applied_at: str


def build_application_created_meta(
    *,
    vacancy_id: UUID,
    resume_document_id: UUID | None,
    cover_letter_document_id: UUID | None,
) -> ApplicationCreatedEventMeta:
    return {
        "vacancy_id": str(vacancy_id),
        "resume_document_id": str(resume_document_id) if resume_document_id else None,
        "cover_letter_document_id": (
            str(cover_letter_document_id) if cover_letter_document_id else None
        ),
    }


def build_application_status_changed_meta(
    *,
    previous_status: str | None,
    new_status: str,
    source: str,
) -> ApplicationStatusChangedEventMeta:
    return {
        "previous_status": previous_status,
        "new_status": new_status,
        "source": source,
    }


def build_application_applied_meta(
    *,
    source: str,
    external_link: str | None,
    applied_at: datetime,
) -> ApplicationAppliedEventMeta:
    return {
        "source": source,
        "external_link": external_link,
        "applied_at": applied_at.isoformat(),
    }
