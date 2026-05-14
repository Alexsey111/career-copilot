"""Domain enum for pipeline execution events."""

from __future__ import annotations

from enum import Enum


class ExecutionEventType(str, Enum):
    EXECUTION_STARTED = "execution_started"
    EVALUATION_COMPLETED = "evaluation_completed"
    RECOMMENDATION_APPLIED = "recommendation_applied"
    REVIEW_COMPLETED = "review_completed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
