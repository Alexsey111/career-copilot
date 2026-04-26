from app.services.interview_preparation_service import InterviewPreparationService


def test_interview_preparation_builds_questions_from_analysis_and_achievements() -> None:
    service = InterviewPreparationService()

    questions = service._build_question_set(
        vacancy_title="Backend Developer",
        company="Test Company",
        must_have=[
            {"text": "Python"},
            {"text": "FastAPI"},
        ],
        nice_to_have=[
            {"text": "Docker"},
        ],
        strengths=[
            {
                "keyword": "Python",
                "scope": "must_have",
                "requirement_text": "Python",
            }
        ],
        gaps=[
            {
                "keyword": "FastAPI",
                "scope": "must_have",
                "requirement_text": "FastAPI",
            }
        ],
        achievements=[
            {
                "title": "Создание ИИ-системы мониторинга безопасности",
                "fact_status": "needs_confirmation",
            }
        ],
    )

    question_types = {item["type"] for item in questions}

    assert "role_overview" in question_types
    assert "must_have_requirement" in question_types
    assert "gap_preparation" in question_types
    assert "strength_deep_dive" in question_types
    assert "achievement_star_story" in question_types

    gap_question = next(item for item in questions if item["type"] == "gap_preparation")
    assert gap_question["keyword"] == "FastAPI"
    assert "does not strongly prove it" in gap_question["prompt"]

    achievement_question = next(
        item for item in questions if item["type"] == "achievement_star_story"
    )
    assert achievement_question["fact_status"] == "needs_confirmation"
    assert "STAR" in achievement_question["prompt"]