from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.application_tracking_service import ApplicationTrackingService


def test_application_status_transition_allows_valid_flow() -> None:
    service = ApplicationTrackingService()

    service._validate_status_transition(
        current_status="draft",
        next_status="submitted",
    )
    service._validate_status_transition(
        current_status="submitted",
        next_status="interview",
    )
    service._validate_status_transition(
        current_status="interview",
        next_status="offer",
    )


def test_application_status_transition_allows_same_status_for_notes_update() -> None:
    service = ApplicationTrackingService()

    service._validate_status_transition(
        current_status="submitted",
        next_status="submitted",
    )
    service._validate_status_transition(
        current_status="rejected",
        next_status="rejected",
    )
    service._validate_status_transition(
        current_status="offer",
        next_status="offer",
    )


@pytest.mark.parametrize(
    ("current_status", "next_status"),
    [
        ("draft", "offer"),
        ("draft", "interview"),
        ("submitted", "draft"),
        ("interview", "submitted"),
        ("rejected", "submitted"),
        ("offer", "draft"),
    ],
)
def test_application_status_transition_rejects_invalid_flow(
    current_status: str,
    next_status: str,
) -> None:
    service = ApplicationTrackingService()

    with pytest.raises(HTTPException) as exc_info:
        service._validate_status_transition(
            current_status=current_status,
            next_status=next_status,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        f"invalid application status transition: {current_status} -> {next_status}"
    )