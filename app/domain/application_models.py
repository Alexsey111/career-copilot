# app/domain/application_models.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ApplicationStatus = Literal[
    "draft",
    "ready",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]

EventType = Literal[
    "applied",
    "status_changed",
    "interview_scheduled",
    "note_added",
    "document_attached",
    "external_link_added",
]


ALLOWED_STATUS_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    "draft": {"ready", "draft"},
    "ready": {"applied", "draft"},
    "applied": {"screening", "interview", "rejected", "withdrawn"},
    "screening": {"interview", "rejected", "withdrawn"},
    "interview": {"offer", "rejected", "withdrawn"},
    "offer": set(),  # финальное состояние
    "rejected": set(),  # финальное состояние
    "withdrawn": set(),  # финальное состояние
}


def is_valid_transition(
    from_status: ApplicationStatus,
    to_status: ApplicationStatus,
) -> bool:
    """Проверяет валидность перехода статуса application."""
    if from_status == to_status:
        return from_status not in {"offer", "rejected", "withdrawn"}

    return to_status in ALLOWED_STATUS_TRANSITIONS.get(from_status, set())


def get_allowed_transitions(status: ApplicationStatus) -> set[ApplicationStatus]:
    """Возвращает допустимые переходы из текущего статуса."""
    return ALLOWED_STATUS_TRANSITIONS.get(status, set())


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
