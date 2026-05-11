# app/schemas/review_workspace.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.readiness_models import ReadinessScore
from app.domain.recommendation_models import RecommendationTask
from app.domain.review_models import (
    ClaimResolution,
    DocumentWarning,
    ReviewDecision,
    ReviewStatus,
)


class ReviewWorkspaceResponse(BaseModel):
    """Complete review workspace for human-in-the-loop operations."""

    # Core identifiers
    workspace_id: str
    document_id: str
    user_id: str
    pipeline_execution_id: str | None = None

    # Document content
    document: dict[str, Any] | None = None
    document_version: str | None = None

    # Evaluation results
    evaluation_report: dict[str, Any] | None = None
    coverage_gaps: list[dict[str, Any]] = Field(default_factory=list)

    # Issues and warnings
    critical_failures: list[DocumentWarning] = Field(default_factory=list)
    warnings: list[DocumentWarning] = Field(default_factory=list)

    # Claims management
    claims_needing_confirmation: list[ClaimResolution] = Field(default_factory=list)
    resolved_claims: list[ClaimResolution] = Field(default_factory=list)

    # Recommendations and readiness
    recommendation_tasks: list[RecommendationTask] = Field(default_factory=list)
    readiness_score: ReadinessScore | None = None

    # Version comparison
    diff_from_previous: dict[str, Any] = Field(default_factory=dict)
    previous_version_id: str | None = None

    # Session metadata
    status: ReviewStatus = "draft"
    created_at: datetime
    updated_at: datetime
    reviewer_id: str | None = None

    # Review decisions
    review_decision: ReviewDecision | None = None

    # Computed properties
    has_critical_issues: bool = Field(default=False)
    review_priority: str = Field(default="low")
    completion_percentage: float = Field(default=0.0)
    actionable_items_count: int = Field(default=0)

    model_config = ConfigDict(from_attributes=True)


class ReviewWorkspaceSummary(BaseModel):
    """Summary view of review workspace for listings."""

    workspace_id: str
    document_id: str
    user_id: str
    status: ReviewStatus
    has_critical_issues: bool
    review_priority: str
    completion_percentage: float
    actionable_items_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewWorkspaceUpdateRequest(BaseModel):
    """Request to update review workspace status."""

    status: ReviewStatus | None = None
    reviewer_id: str | None = None
    review_decision: ReviewDecision | None = None