# app\domain\application_statuses.py

from __future__ import annotations

from app.domain.application_status import (
    ALLOWED_TRANSITIONS,
    APPLICATION_STATUSES as APPLICATION_STATUS_ENUMS,
    ApplicationStatus,
)

APPLICATION_STATUSES: set[str] = {status.value for status in APPLICATION_STATUS_ENUMS}
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    status.value: {transition.value for transition in transitions}
    for status, transitions in ALLOWED_TRANSITIONS.items()
}

APPLICATION_STATUS_DRAFT = ApplicationStatus.DRAFT.value
APPLICATION_STATUS_READY = ApplicationStatus.READY.value
APPLICATION_STATUS_APPLIED = ApplicationStatus.APPLIED.value
APPLICATION_STATUS_SCREENING = ApplicationStatus.SCREENING.value
APPLICATION_STATUS_INTERVIEW = ApplicationStatus.INTERVIEW.value
APPLICATION_STATUS_OFFER = ApplicationStatus.OFFER.value
APPLICATION_STATUS_REJECTED = ApplicationStatus.REJECTED.value
APPLICATION_STATUS_WITHDRAWN = ApplicationStatus.WITHDRAWN.value
