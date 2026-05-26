from __future__ import annotations

from enum import StrEnum


class ApplicationEventType(StrEnum):
    APPLICATION_CREATED = "application_created"
    APPLICATION_READY = "application_ready"
    APPLICATION_APPLIED = "application_applied"
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    APPLICATION_REVIEW_REQUIRED = "application_review_required"
    DOCUMENT_ATTACHED = "document_attached"
    NOTE_ADDED = "note_added"
    INTERVIEW_SESSION_CREATED = "interview_session_created"
    OUTCOME_RECORDED = "outcome_recorded"
    EXTERNAL_LINK_ADDED = "external_link_added"


def normalize_application_event_type(
    value: str | ApplicationEventType,
) -> ApplicationEventType | None:
    if isinstance(value, ApplicationEventType):
        return value

    try:
        return ApplicationEventType(value)
    except ValueError:
        return None
