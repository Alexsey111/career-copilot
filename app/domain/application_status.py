from __future__ import annotations

from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


APPLICATION_STATUSES: set[ApplicationStatus] = set(ApplicationStatus)

FINAL_APPLICATION_STATUSES: set[ApplicationStatus] = {
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}

ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DRAFT: {
        ApplicationStatus.READY,
        ApplicationStatus.DRAFT,
    },
    ApplicationStatus.READY: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.DRAFT,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.SCREENING,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.SCREENING: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFER: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}


def normalize_application_status(
    value: str | ApplicationStatus,
) -> ApplicationStatus | None:
    if isinstance(value, ApplicationStatus):
        return value

    try:
        return ApplicationStatus(value)
    except ValueError:
        return None
