# app/services/document_serialization.py

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.domain.document_models import (
    GapMitigation,
    MatchKeywordSet,
    SelectedAchievement,
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


def serialize_achievement(
    achievement: SelectedAchievement,
) -> dict:
    """Сериализация SelectedAchievement в JSON-совместимый dict."""
    return to_jsonable(achievement)


def serialize_keyword_set(
    keyword_set: MatchKeywordSet,
) -> dict:
    """Сериализация MatchKeywordSet в JSON-совместимый dict."""
    return to_jsonable(keyword_set)


def serialize_gap_mitigation(
    gap_mitigation: GapMitigation,
) -> dict:
    """Сериализация GapMitigation в JSON-совместимый dict."""
    return to_jsonable(gap_mitigation)
