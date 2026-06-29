# app\services\document_evidence_guards.py

from __future__ import annotations

import re
from typing import Any


_REPOSITORY_SIGNAL_MARKERS = (
    "repository evidence",
    "repository signal",
    "implementation signals",
    "implementation signal",
    "backend-related implementation",
    "technical implementation",
    "github_repository_analysis",
)


def is_repository_evidence_signal(value: Any) -> bool:
    if isinstance(value, dict):
        parts = [
            value.get("title"),
            value.get("summary"),
            value.get("evidence_note"),
            value.get("source"),
            value.get("type"),
            value.get("snippet_text"),
            value.get("action"),
            value.get("task"),
            " ".join(str(item) for item in value.get("signals") or []),
        ]
        text = " ".join(str(part or "") for part in parts)
    else:
        text = str(value or "")

    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    if not normalized:
        return False

    return any(marker in normalized for marker in _REPOSITORY_SIGNAL_MARKERS)


def filter_user_facing_achievements(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if is_repository_evidence_signal(item):
            continue
        result.append(item)
    return result