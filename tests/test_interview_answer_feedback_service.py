from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.interview_preparation_service import InterviewPreparationService


def test_interview_answers_validate_question_index_and_duplicate_answers() -> None:
    service = InterviewPreparationService()
    question_set = [{"type": "role_overview"}, {"type": "gap_preparation"}]

    normalized = service._validate_and_normalize_answers(
        question_set=question_set,
        answers=[
            {"question_index": 0, "answer_text": "Test answer"},
        ],
    )

    assert normalized == [
        {
            "question_index": 0,
            "question_type": "role_overview",
            "answer_format": None,
            "answer_text": "Test answer",
        }
    ]

    with pytest.raises(HTTPException) as out_of_range:
        service._validate_and_normalize_answers(
            question_set=question_set,
            answers=[
                {"question_index": 5, "answer_text": "Bad index"},
            ],
        )

    assert out_of_range.value.status_code == 400
    assert out_of_range.value.detail == "question_index out of range: 5"

    with pytest.raises(HTTPException) as duplicate:
        service._validate_and_normalize_answers(
            question_set=question_set,
            answers=[
                {"question_index": 1, "answer_text": "First"},
                {"question_index": 1, "answer_text": "Second"},
            ],
        )

    assert duplicate.value.status_code == 400
    assert duplicate.value.detail == "duplicate answer for question_index: 1"


def test_interview_feedback_flags_weak_star_gap_overclaim_and_metrics() -> None:
    service = InterviewPreparationService()

    question_set = [
        {
            "type": "strength_deep_dive",
            "answer_format": "STAR",
        },
        {
            "type": "gap_preparation",
            "answer_format": "honest_gap_response",
        },
        {
            "type": "achievement_star_story",
            "answer_format": "STAR",
        },
    ]

    feedback = service._build_feedback(
        question_set=question_set,
        answers=[
            {
                "question_index": 0,
                "question_type": "strength_deep_dive",
                "answer_format": "STAR",
                "answer_text": "I used Python.",
            },
            {
                "question_index": 1,
                "question_type": "gap_preparation",
                "answer_format": "honest_gap_response",
                "answer_text": "I have commercial experience and expert level in Redis.",
            },
            {
                "question_index": 2,
                "question_type": "achievement_star_story",
                "answer_format": "STAR",
                "answer_text": (
                    "Situation: task was quality control. "
                    "Action: I built a prototype. "
                    "Result: improved speed by 35%."
                ),
            },
        ],
    )

    items = feedback["items"]

    assert "weak_star_structure" in items[0]["warnings"]
    assert "possible_gap_overclaim" in items[1]["warnings"]
    assert "metric_needs_confirmation" in items[2]["warnings"]

    score = service._build_score(feedback)
    assert score["answered_count"] == 3
    assert score["warning_count"] == 3
    assert score["readiness_score"] == 55