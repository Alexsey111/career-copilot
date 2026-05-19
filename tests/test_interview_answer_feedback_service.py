from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.interview_preparation_service import InterviewPreparationService


def test_interview_answers_validate_question_index_and_duplicate_answers() -> None:
    service = InterviewPreparationService()
    question_set = [
        {"question_id": "iq_role", "type": "role_overview"},
        {"question_id": "iq_gap", "type": "gap_preparation"},
    ]

    normalized = service._validate_and_normalize_answers(
        question_set=question_set,
        answers=[
            {
                "question_id": "iq_role",
                "question_index": 0,
                "answer_text": "Test answer",
            },
        ],
    )

    assert normalized == [
        {
            "question_id": "iq_role",
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
                {
                    "question_id": "iq_missing",
                    "question_index": 5,
                    "answer_text": "Bad index",
                },
            ],
        )

    assert out_of_range.value.status_code == 400
    assert out_of_range.value.detail == "question_index out of range: 5"

    with pytest.raises(HTTPException) as mismatch:
        service._validate_and_normalize_answers(
            question_set=question_set,
            answers=[
                {
                    "question_id": "iq_wrong",
                    "question_index": 1,
                    "answer_text": "Mismatch",
                },
            ],
        )

    assert mismatch.value.status_code == 400
    assert mismatch.value.detail == "question_id does not match question_index: 1"

    with pytest.raises(HTTPException) as duplicate:
        service._validate_and_normalize_answers(
            question_set=question_set,
            answers=[
                {
                    "question_id": "iq_gap",
                    "question_index": 1,
                    "answer_text": "First",
                },
                {
                    "question_id": "iq_gap",
                    "question_index": 1,
                    "answer_text": "Second",
                },
            ],
        )

    assert duplicate.value.status_code == 400
    assert duplicate.value.detail == "duplicate answer for question_index: 1"


def test_interview_feedback_flags_weak_star_gap_overclaim_and_metrics() -> None:
    service = InterviewPreparationService()

    question_set = [
        {
            "question_id": "iq_strength",
            "type": "strength_deep_dive",
            "answer_format": "STAR",
            "competency_key": "backend_api_design",
            "competency_name": "Backend API design",
        },
        {
            "question_id": "iq_gap",
            "type": "gap_preparation",
            "answer_format": "honest_gap_response",
            "competency_key": "gap_handling",
            "competency_name": "Gap handling",
        },
        {
            "question_id": "iq_achievement",
            "type": "achievement_star_story",
            "answer_format": "STAR",
        },
    ]

    feedback = service._build_feedback(
        question_set=question_set,
        answers=[
            {
                "question_id": "iq_strength",
                "question_index": 0,
                "question_type": "strength_deep_dive",
                "answer_format": "STAR",
                "answer_text": "I used Python.",
            },
            {
                "question_id": "iq_gap",
                "question_index": 1,
                "question_type": "gap_preparation",
                "answer_format": "honest_gap_response",
                "answer_text": "I have commercial experience and expert level in Redis.",
            },
            {
                "question_id": "iq_achievement",
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

    assert items[0]["question_id"] == "iq_strength"
    assert "weak_star_structure" in items[0]["warnings"]
    assert "possible_gap_overclaim" in items[1]["warnings"]
    assert "metric_needs_confirmation" in items[2]["warnings"]

    score = service._build_score(feedback, question_set=question_set)
    assert score["answered_count"] == 3
    assert score["warning_count"] == 3
    assert score["readiness_score"] == 55
    assert score["score_version"] == "deterministic_v3"
    assert len(score["competency_readiness"]) == 2

    backend_competency = next(
        item
        for item in score["competency_readiness"]
        if item["competency_key"] == "backend_api_design"
    )
    assert backend_competency["question_count"] == 1
    assert backend_competency["answered_count"] == 1
    assert backend_competency["warning_count"] == 1
    assert backend_competency["readiness_score"] == 85

    gap_competency = next(
        item
        for item in score["competency_readiness"]
        if item["competency_key"] == "gap_handling"
    )
    assert gap_competency["question_count"] == 1
    assert gap_competency["answered_count"] == 1
    assert gap_competency["warning_count"] == 1
    assert gap_competency["readiness_score"] == 85


def test_interview_score_ignores_questions_without_competency_key() -> None:
    service = InterviewPreparationService()

    question_set = [
        {
            "question_id": "iq_1",
            "type": "achievement_star_story",
            "answer_format": "STAR",
        }
    ]
    feedback = {
        "items": [
            {
                "question_id": "iq_1",
                "question_index": 0,
                "question_type": "achievement_star_story",
                "warnings": [],
                "suggestions": [],
                "answer_length": 42,
            }
        ]
    }

    score = service._build_score(feedback, question_set=question_set)

    assert score["readiness_score"] == 100
    assert score["competency_readiness"] == []


def test_interview_score_unanswered_competency_lowers_readiness() -> None:
    service = InterviewPreparationService()

    question_set = [
        {
            "question_id": "iq_1",
            "type": "must_have_requirement",
            "answer_format": "STAR_or_example",
            "competency_key": "backend_api_design",
            "competency_name": "Backend API design",
        },
        {
            "question_id": "iq_2",
            "type": "strength_deep_dive",
            "answer_format": "STAR",
            "competency_key": "backend_api_design",
            "competency_name": "Backend API design",
        },
    ]
    feedback = {
        "items": [
            {
                "question_id": "iq_1",
                "question_index": 0,
                "question_type": "must_have_requirement",
                "warnings": [],
                "suggestions": [],
                "answer_length": 120,
            }
        ]
    }

    score = service._build_score(feedback, question_set=question_set)

    competency = score["competency_readiness"][0]
    assert competency["question_count"] == 2
    assert competency["answered_count"] == 1
    assert competency["warning_count"] == 0
    assert competency["readiness_score"] == 92


def test_interview_score_warning_lowers_competency_readiness() -> None:
    service = InterviewPreparationService()

    question_set = [
        {
            "question_id": "iq_1",
            "type": "must_have_requirement",
            "answer_format": "STAR_or_example",
            "competency_key": "backend_api_design",
            "competency_name": "Backend API design",
        }
    ]
    feedback = {
        "items": [
            {
                "question_id": "iq_1",
                "question_index": 0,
                "question_type": "must_have_requirement",
                "warnings": ["weak_star_structure"],
                "suggestions": [],
                "answer_length": 120,
            }
        ]
    }

    score = service._build_score(feedback, question_set=question_set)

    competency = score["competency_readiness"][0]
    assert competency["readiness_score"] == 85
