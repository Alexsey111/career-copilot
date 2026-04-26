from app.services.resume_generation_service import ResumeGenerationService


def test_resume_generation_extracts_match_keywords_from_analysis_json() -> None:
    service = ResumeGenerationService()

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


def test_resume_generation_skill_matching_does_not_overclaim_specific_db() -> None:
    service = ResumeGenerationService()

    assert service._skill_matches_keyword("SQL", "PostgreSQL") is False
    assert service._skill_matches_keyword("PostgreSQL", "SQL") is True
    assert service._skill_matches_keyword("API", "FastAPI") is False
    assert service._skill_matches_keyword("FastAPI", "API") is True


def test_resume_generation_selects_matched_skills_first_without_claiming_gaps() -> None:
    service = ResumeGenerationService()

    selected = service._select_resume_skills(
        raw_skills=["Python", "SQL", "API", "Docker", "LLM"],
        matched_keywords=["Python", "Docker"],
    )

    assert selected[:2] == ["Python", "Docker"]
    assert "SQL" in selected
    assert "API" in selected


def test_resume_rendered_text_does_not_include_internal_review_notes() -> None:
    service = ResumeGenerationService()

    rendered = service._render_resume_text(
        {
            "candidate": {
                "full_name": "Test User",
                "headline": "AI Product Engineer",
                "location": "Remote",
            },
            "target_vacancy": {
                "title": "Backend Developer",
            },
            "sections": {
                "summary_bullets": ["Profile-confirmed relevant skills: Python."],
                "skills": ["Python", "Docker"],
                "experience": [],
                "selected_achievements": [],
                "warnings": ["missing or weakly represented vacancy keywords: FastAPI"],
                "fit_summary": {"match_score": 27},
            },
        }
    )

    assert "Test User" in rendered
    assert "SUMMARY" in rendered
    assert "SKILLS" in rendered
    assert "REVIEW NOTES" not in rendered
    assert "FIT SUMMARY" not in rendered
    assert "Match score" not in rendered
    assert "missing or weakly represented" not in rendered