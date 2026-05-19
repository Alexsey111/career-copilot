# app/services/interview_serialization.py

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from typing import Any

from app.domain.interview_models import (
    InterviewFeedbackDraft,
    InterviewQuestionDraft,
    InterviewScoreDraft,
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


def serialize_question(
    question: InterviewQuestionDraft,
    *,
    index: int | None = None,
) -> dict:
    """Сериализация InterviewQuestionDraft в JSON-совместимый dict."""
    payload = to_jsonable(question)
    if payload.get("question_id"):
        return payload

    identity_payload = {
        "index": index,
        "type": payload.get("type"),
        "source": payload.get("source"),
        "prompt": payload.get("prompt"),
        "answer_format": payload.get("answer_format"),
        "rubric": payload.get("rubric", []),
        "competency_key": payload.get("competency_key"),
        "competency_name": payload.get("competency_name"),
        "keyword": payload.get("keyword"),
        "requirement_text": payload.get("requirement_text"),
        "achievement_title": payload.get("achievement_title"),
        "fact_status": payload.get("fact_status"),
    }
    serialized_identity = json.dumps(
        identity_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload["question_id"] = "iq_" + hashlib.sha1(
        serialized_identity.encode("utf-8")
    ).hexdigest()[:16]
    return payload


def serialize_feedback(
    feedback: InterviewFeedbackDraft,
) -> dict:
    """Сериализация InterviewFeedbackDraft в JSON-совместимый dict."""
    return to_jsonable(feedback)


def serialize_score(
    score: InterviewScoreDraft,
) -> dict:
    """Сериализация InterviewScoreDraft в JSON-совместимый dict."""
    return to_jsonable(score)
