# app/domain/review_models.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ReviewStatus = Literal[
    "draft",
    "review_required",
    "reviewed",
    "approved",
    "archived",
]

ReviewerAction = Literal[
    "accept_all",
    "reject_all",
    "accept_selected",
    "reject_selected",
    "edit_and_accept",
]

WarningSeverity = Literal[
    "info",
    "warning",
    "critical",
]


@dataclass(slots=True)
class ClaimReviewDecision:
    """Решение ревьюера по отдельному claim."""
    claim_text: str
    action: str  # "accepted", "rejected", "edited"
    edited_text: str | None = None
    reviewed_at: datetime | None = None
    reviewer_id: str | None = None


@dataclass(slots=True)
class ReviewDecision:
    """Общее решение ревьюера по документу."""
    reviewer_action: ReviewerAction
    accepted_claims: list[ClaimReviewDecision] = field(default_factory=list)
    rejected_claims: list[ClaimReviewDecision] = field(default_factory=list)
    edited_sections: list[str] = field(default_factory=list)
    final_status: ReviewStatus = "reviewed"
    reviewed_at: datetime | None = None
    reviewer_comment: str | None = None


@dataclass(slots=True)
class DocumentWarning:
    """Предупреждение с уровнем severity."""
    code: str
    message: str
    severity: WarningSeverity
    section: str | None = None
    claim_text: str | None = None


@dataclass(slots=True)
class ClaimResolution:
    """Решение по claim в контексте всего документа."""
    claim_text: str
    fact_status: str  # "confirmed", "rejected", "needs_confirmation"
    resolved_at: datetime | None = None
    resolution_reason: str | None = None


ALLOWED_STATUS_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    "draft": {"review_required", "approved", "draft"},  # approved для backward compatibility
    "review_required": {"reviewed", "draft"},
    "reviewed": {"approved", "review_required", "draft"},
    "approved": {"archived", "review_required"},
    "archived": set(),  # archived - конечное состояние
}


def is_valid_transition(
    from_status: ReviewStatus,
    to_status: ReviewStatus,
) -> bool:
    """Проверяет валидность перехода статуса документа."""
    return to_status in ALLOWED_STATUS_TRANSITIONS.get(from_status, set())


def get_allowed_transitions(status: ReviewStatus) -> set[ReviewStatus]:
    """Возвращает допустимые переходы из текущего статуса."""
    return ALLOWED_STATUS_TRANSITIONS.get(status, set())
