# app/domain/application_models.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain.application_status import (
    ALLOWED_TRANSITIONS,
    ApplicationStatus,
    FINAL_APPLICATION_STATUSES,
    normalize_application_status,
)

EventType = Literal[
    "applied",
    "status_changed",
    "interview_scheduled",
    "note_added",
    "document_attached",
    "external_link_added",
]


ALLOWED_STATUS_TRANSITIONS = ALLOWED_TRANSITIONS


def is_valid_transition(
    from_status: str | ApplicationStatus,
    to_status: str | ApplicationStatus,
) -> bool:
    """Проверяет валидность перехода статуса application."""
    normalized_from_status = normalize_application_status(from_status)
    normalized_to_status = normalize_application_status(to_status)

    if normalized_from_status is None or normalized_to_status is None:
        return False

    if normalized_from_status == normalized_to_status:
        return normalized_from_status not in FINAL_APPLICATION_STATUSES

    return normalized_to_status in ALLOWED_STATUS_TRANSITIONS.get(
        normalized_from_status,
        set(),
    )


def get_allowed_transitions(status: str | ApplicationStatus) -> set[str]:
    """Возвращает допустимые переходы из текущего статуса."""
    normalized_status = normalize_application_status(status)
    if normalized_status is None:
        return set()

    return {
        transition.value
        for transition in ALLOWED_STATUS_TRANSITIONS.get(normalized_status, set())
    }


@dataclass(slots=True)
class ApplicationSnapshot:
    """Snapshot приложенных документов."""
    resume_document_id: str | None = None
    resume_document_version: str | None = None
    cover_letter_document_id: str | None = None
    cover_letter_document_version: str | None = None


@dataclass(slots=True)
class ApplicationEventRecord:
    """Запись события в timeline."""
    event_type: EventType
    title: str | None = None
    description: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
