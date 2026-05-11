# app/domain/review_models.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.domain.readiness_models import ReadinessScore
from app.domain.recommendation_models import RecommendationTask

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


@dataclass(slots=True)
class ReviewSession:
    """Human review workspace containing all review-related information."""
    session_id: str
    document_id: str
    user_id: str

    # Core review content
    unresolved_claims: list[ClaimResolution] = field(default_factory=list)
    warnings: list[DocumentWarning] = field(default_factory=list)
    critical_failures: list[DocumentWarning] = field(default_factory=list)
    recommendations: list[RecommendationTask] = field(default_factory=list)

    # Readiness analysis
    readiness_score: ReadinessScore | None = None
    readiness_blockers: list[str] = field(default_factory=list)

    # Version comparison
    previous_version_id: str | None = None
    version_diff: dict = field(default_factory=dict)  # Document diff data

    # Session metadata
    status: ReviewStatus = "draft"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reviewer_id: str | None = None

    # Review decisions (populated during review)
    review_decision: ReviewDecision | None = None

    @property
    def has_critical_issues(self) -> bool:
        """Check if session has critical failures or readiness blockers."""
        return (
            len(self.critical_failures) > 0 or
            len(self.readiness_blockers) > 0 or
            (self.readiness_score and not self.readiness_score.is_ready)
        )

    @property
    def review_priority(self) -> str:
        """Calculate review priority based on issues."""
        if self.has_critical_issues:
            return "high"
        if len(self.warnings) > 5 or len(self.unresolved_claims) > 10:
            return "medium"
        return "low"

    @property
    def completion_percentage(self) -> float:
        """Calculate session completion percentage."""
        total_items = (
            len(self.unresolved_claims) +
            len(self.warnings) +
            len(self.critical_failures) +
            len(self.recommendations)
        )
        if total_items == 0:
            return 100.0

        # Assume completion based on resolved items (simplified)
        resolved_items = sum(1 for claim in self.unresolved_claims if claim.fact_status != "needs_confirmation")
        return min(100.0, (resolved_items / total_items) * 100.0)


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


@dataclass(slots=True)
class ReviewWorkspace:
    """Unified review aggregate for human-in-the-loop operating surface."""

    # Core identifiers
    workspace_id: str
    document_id: str
    user_id: str
    pipeline_execution_id: str | None = None

    # Document content
    document: dict[str, Any] | None = None  # Full document data
    document_version: str | None = None

    # Evaluation results
    evaluation_report: dict[str, Any] | None = None  # Full evaluation data
    coverage_gaps: list[dict[str, Any]] = field(default_factory=list)  # Coverage analysis gaps

    # Issues and warnings
    critical_failures: list[DocumentWarning] = field(default_factory=list)
    warnings: list[DocumentWarning] = field(default_factory=list)

    # Claims management
    claims_needing_confirmation: list[ClaimResolution] = field(default_factory=list)
    resolved_claims: list[ClaimResolution] = field(default_factory=list)

    # Recommendations and readiness
    recommendation_tasks: list[RecommendationTask] = field(default_factory=list)
    readiness_score: ReadinessScore | None = None

    # Version comparison
    diff_from_previous: dict[str, Any] = field(default_factory=dict)
    previous_version_id: str | None = None

    # Session metadata
    status: ReviewStatus = "draft"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reviewer_id: str | None = None

    # Review decisions (when completed)
    review_decision: ReviewDecision | None = None

    @property
    def has_critical_issues(self) -> bool:
        """Check if workspace has critical issues requiring attention."""
        return (
            len(self.critical_failures) > 0 or
            len(self.claims_needing_confirmation) > 0 or
            (self.readiness_score and not self.readiness_score.is_ready)
        )

    @property
    def review_priority(self) -> str:
        """Calculate review priority based on issues."""
        if self.has_critical_issues:
            return "high"
        if len(self.warnings) > 3 or len(self.claims_needing_confirmation) > 5:
            return "medium"
        return "low"

    @property
    def completion_percentage(self) -> float:
        """Calculate workspace completion percentage."""
        total_items = (
            len(self.claims_needing_confirmation) +
            len(self.warnings) +
            len(self.critical_failures) +
            len(self.recommendation_tasks)
        )
        if total_items == 0:
            return 100.0

        # Count resolved items
        resolved_claims = len(self.resolved_claims)
        return min(100.0, (resolved_claims / total_items) * 100.0)

    @property
    def actionable_items_count(self) -> int:
        """Count of items requiring human action."""
        return (
            len(self.claims_needing_confirmation) +
            len(self.warnings) +
            len(self.critical_failures) +
            len(self.recommendation_tasks)
        )
