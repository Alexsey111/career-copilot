"""Failure classification models for operational pipeline handling."""

from __future__ import annotations

from enum import Enum


class FailureCategory(str, Enum):
    TRANSIENT = "transient"
    DEPENDENCY = "dependency"
    VALIDATION = "validation"
    PERMANENT = "permanent"


def classify_failure(exc: Exception) -> FailureCategory:
    if isinstance(exc, ValueError):
        return FailureCategory.VALIDATION
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return FailureCategory.DEPENDENCY
    if isinstance(exc, RuntimeError):
        return FailureCategory.TRANSIENT
    return FailureCategory.PERMANENT


def is_retryable_failure(category: FailureCategory) -> bool:
    return category in {
        FailureCategory.TRANSIENT,
        FailureCategory.DEPENDENCY,
    }
