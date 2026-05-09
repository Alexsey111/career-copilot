# app/services/interview_serialization.py

from __future__ import annotations

from dataclasses import asdict, is_dataclass
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
) -> dict:
    """Сериализация InterviewQuestionDraft в JSON-совместимый dict."""
    return to_jsonable(question)


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
