from types import SimpleNamespace

from app.services.cover_letter_generation_service import CoverLetterGenerationService


def test_cover_letter_generation_uses_analysis_strengths_and_gaps_as_truth() -> None:
    service = CoverLetterGenerationService()

    matched, missing = service._extract_match_keywords_from_analysis(
        strengths_json=[
            {"keyword": "Python", "scope": "must_have"},
            {"keyword": "Docker", "scope": "nice_to_have"},
        ],
        gaps_json=[
            {"keyword": "FastAPI", "scope": "must_have"},
            {"keyword": "Redis", "scope": "nice_to_have"},
        ],
    )

    assert matched == ["Python", "Docker"]
    assert missing == ["FastAPI", "Redis"]


def test_cover_letter_relevance_paragraph_does_not_include_missing_keywords() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["Python"],
        selected_achievements=[],
    )

    assert "Python" in paragraph
    assert "Redis" not in paragraph
    assert "PostgreSQL" not in paragraph
    assert "подтверждённое пересечение" in paragraph
    assert "confirmed overlap" not in paragraph


def test_cover_letter_warnings_keep_missing_keywords_out_of_rendered_letter() -> None:
    service = CoverLetterGenerationService()

    content_json = {
        "sections": {
            "opening": "Здравствуйте!\n\nРассматриваю вакансию Backend Developer.",
            "relevance_paragraph": (
                "По текущему профилю наиболее подтверждённое пересечение "
                "с вакансией: Python."
            ),
            "closing": "Буду рад обсудить, как мой опыт может быть полезен.",
            "warnings": [
                "profile does not strongly support these vacancy keywords yet: Redis, PostgreSQL"
            ],
        }
    }

    rendered = service._render_cover_letter(content_json)

    assert "Python" in rendered
    assert "Здравствуйте" in rendered
    assert "Буду рад обсудить" in rendered
    assert "profile does not strongly support" not in rendered
    assert "Redis" not in rendered
    assert "PostgreSQL" not in rendered


def test_cover_letter_rendered_text_is_russian_and_not_internal_copy() -> None:
    service = CoverLetterGenerationService()

    opening = service._build_opening(
        full_name="Перминов Алексей",
        vacancy_title="Backend Developer",
        company="Test Company",
        headline="Prompt Engineering, Data Science, Vibe-coding",
    )
    relevance = service._build_relevance_paragraph(
        matched_keywords=["Python"],
        selected_achievements=[
            {
                "title": "Создание ИИ-системы для мониторинга безопасности",
                "fact_status": "needs_confirmation",
                "reason": "ai_relevance",
            }
        ],
    )
    closing = service._build_closing(
        vacancy_title="Backend Developer",
        company="Test Company",
    )

    rendered = service._render_cover_letter(
        {
            "sections": {
                "opening": opening,
                "relevance_paragraph": relevance,
                "closing": closing,
                "warnings": [],
            }
        }
    )

    assert "Здравствуйте" in rendered
    assert "Меня зовут Перминов Алексей" in rendered
    assert "Рассматриваю вакансию Backend Developer" in rendered
    assert "По текущему профилю" in rendered
    assert "Буду рад обсудить" in rendered

    assert "Dear hiring team" not in rendered
    assert "Thank you for your consideration" not in rendered
    assert "confirmed overlap" not in rendered
    assert "needs_confirmation" not in rendered


def test_cover_letter_generation_uses_only_confirmed_achievement_titles() -> None:
    service = CoverLetterGenerationService()

    achievements = [
        SimpleNamespace(
            title="Подтверждённый AI-проект",
            fact_status="confirmed",
        ),
        SimpleNamespace(
            title="Неподтверждённый проект",
            fact_status="needs_confirmation",
        ),
        SimpleNamespace(
            title="",
            fact_status="confirmed",
        ),
    ]

    titles = service._get_confirmed_achievement_titles(achievements)

    assert titles == ["Подтверждённый AI-проект"]


def test_cover_letter_selected_achievements_are_confirmed_and_do_not_create_claims() -> None:
    service = CoverLetterGenerationService()

    selected = service._select_relevant_achievements(
        achievement_titles=["Подтверждённый AI-проект"],
        keywords=["Python"],
    )

    assert selected == [
        {
            "title": "Подтверждённый AI-проект",
            "fact_status": "confirmed",
            "reason": "ai_relevance",
        }
    ]

    claims = service._build_claims_needing_confirmation(
        selected_achievements=selected,
    )

    assert claims == []
