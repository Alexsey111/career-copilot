# app/services/trace_serialization.py

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.domain.trace_models import (
    AIAuditMetadata,
    DeterministicCheckResult,
    DocumentEvaluationReport,
    GenerationTrace,
)


def to_jsonable(value: Any) -> Any:
    """Рекурсивная сериализация dataclass'ов в JSON-совместимый dict."""
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json"))
    return value


def serialize_trace(
    trace: GenerationTrace,
) -> dict:
    """Сериализация GenerationTrace в JSON-совместимый dict."""
    return to_jsonable(trace)


def serialize_ai_metadata(
    metadata: AIAuditMetadata,
) -> dict:
    """Сериализация AIAuditMetadata в JSON-совместимый dict."""
    return to_jsonable(metadata)


def serialize_check_result(
    check: DeterministicCheckResult,
) -> dict:
    """Сериализация DeterministicCheckResult в JSON-совместимый dict."""
    return to_jsonable(check)


def serialize_evaluation_report(
    report: DocumentEvaluationReport,
) -> dict:
    """Сериализация DocumentEvaluationReport в JSON-совместимый dict."""
    return to_jsonable(report)
