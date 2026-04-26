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
    assert "confirmed overlap" in paragraph


def test_cover_letter_warnings_keep_missing_keywords_out_of_rendered_letter() -> None:
    service = CoverLetterGenerationService()

    content_json = {
        "sections": {
            "opening": "Dear hiring team,\n\nI am applying for the Backend Developer role.",
            "relevance_paragraph": "The strongest confirmed overlap in my current profile is with Python.",
            "closing": "Thank you for your consideration.",
            "warnings": [
                "profile does not strongly support these vacancy keywords yet: Redis, PostgreSQL"
            ],
        }
    }

    rendered = service._render_cover_letter(content_json)

    assert "Python" in rendered
    assert "Dear hiring team" in rendered
    assert "Thank you for your consideration" in rendered
    assert "profile does not strongly support" not in rendered
    assert "Redis" not in rendered
    assert "PostgreSQL" not in rendered