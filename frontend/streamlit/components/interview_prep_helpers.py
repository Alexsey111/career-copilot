# frontend\streamlit\components\interview_prep_helpers.py

from __future__ import annotations

from typing import Any
from uuid import UUID

from .interview_prep_formatters import _normalize_key


def _sanitize_evidence_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    blocked_markers = [
        "extracted as a",
        "normalized contribution signal",
        "candidate ownership must be reviewed",
        "before strong use in documents",
        "implementation signal",
        "workflow automation signal",
    ]

    lowered = text.lower()
    cut_positions = [
        lowered.find(marker)
        for marker in blocked_markers
        if lowered.find(marker) >= 0
    ]

    if cut_positions:
        text = text[: min(cut_positions)].strip(" .;:-")

    return text


def _looks_like_uuid(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False

    try:
        UUID(text)
    except ValueError:
        return False

    return True


def _is_insufficient_grounding(answer: dict[str, Any] | None) -> bool:
    if not isinstance(answer, dict):
        return False
    return (
        str(answer.get("grounding_status") or "").strip().lower()
        == "insufficient_evidence"
    )


def _collect_evidence_by_competency(
    *,
    questions: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}

    for question in questions:
        competency_key = _normalize_key(question.get("competency_key"))
        if not competency_key:
            continue

        for item in question.get("recommended_evidence") or []:
            result.setdefault(competency_key, []).append(item)

    for item in evidence_links:
        competency_key = _normalize_key(item.get("competency_key"))
        if not competency_key:
            continue
        result.setdefault(competency_key, []).append(item)

    return result


def _best_fact_status(items: list[dict[str, Any]]) -> str | None:
    statuses = {
        str(item.get("fact_status") or "").strip().lower()
        for item in items
        if str(item.get("fact_status") or "").strip()
    }
    if "confirmed" in statuses:
        return "confirmed"
    if "user_provided" in statuses:
        return "user_provided"
    if "needs_confirmation" in statuses:
        return "needs_confirmation"
    if "partial" in statuses:
        return "partial"
    if statuses:
        return sorted(statuses)[0]
    return None
