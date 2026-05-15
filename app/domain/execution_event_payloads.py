"""Typed payload objects for immutable pipeline execution events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


@dataclass(slots=True, frozen=True)
class ExecutionStartedPayload:
    pipeline_version: str
    calibration_version: str | None = None


@dataclass(slots=True, frozen=True)
class EvaluationCompletedPayload:
    snapshot_id: UUID
    score: float
    duration_ms: int
    phase: str = "initial"


@dataclass(slots=True, frozen=True)
class RecommendationAppliedPayload:
    recommendation_id: str
    task_type: str
    document_id: UUID


@dataclass(slots=True, frozen=True)
class ReviewRequiredPayload:
    review_reason: str | None = None


@dataclass(slots=True, frozen=True)
class ReviewCompletedPayload:
    review_summary: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class EvaluationFailedPayload:
    error_details: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class ExecutionCompletedPayload:
    artifacts_count: int = 0
    metrics_count: int = 0


@dataclass(slots=True, frozen=True)
class ExecutionFailedPayload:
    error_type: str
    message: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True, frozen=True)
class StepStartedPayload:
    step_name: str


@dataclass(slots=True, frozen=True)
class StepCompletedPayload:
    output_artifacts_count: int = 0


@dataclass(slots=True, frozen=True)
class StepFailedPayload:
    error_message: str


def serialize_execution_event_payload(payload: Any | None) -> dict[str, Any]:
    """Convert typed payloads into JSON-serializable dicts."""
    if payload is None:
        return {}
    if is_dataclass(payload):
        return _json_safe(asdict(payload))
    if isinstance(payload, dict):
        return _json_safe(dict(payload))
    if isinstance(payload, str):
        return {"value": payload}
    raise TypeError(f"Unsupported execution event payload type: {type(payload)!r}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
