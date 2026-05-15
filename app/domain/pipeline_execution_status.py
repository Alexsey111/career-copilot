"""Strict state machine statuses for pipeline execution lifecycle."""

from __future__ import annotations

from enum import Enum


class PipelineExecutionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

