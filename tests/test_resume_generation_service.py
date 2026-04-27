from types import SimpleNamespace

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
                "summary_bullets": [
                    "Подтверждённые пересечения с вакансией Backend Developer: Python."
                ],
                "skills": ["Python", "Docker"],
                "experience": [],
                "selected_achievements": [
                    {
                        "title": "Создание ИИ-системы для мониторинга безопасности",
                        "fact_status": "needs_confirmation",
                    }
                ],
                "warnings": ["missing or weakly represented vacancy keywords: FastAPI"],
                "fit_summary": {"match_score": 27},
            },
        }
    )

    assert "Test User" in rendered
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in rendered
    assert "КРАТКОЕ РЕЗЮМЕ" in rendered
    assert "КЛЮЧЕВЫЕ НАВЫКИ" in rendered
    assert "РЕЛЕВАНТНЫЕ ПРОЕКТЫ" in rendered

    assert "SUMMARY" not in rendered
    assert "SKILLS" not in rendered
    assert "EXPERIENCE" not in rendered
    assert "REVIEW NOTES" not in rendered
    assert "FIT SUMMARY" not in rendered
    assert "Match score" not in rendered
    assert "missing or weakly represented" not in rendered
    assert "needs_confirmation" not in rendered


def test_resume_summary_bullets_are_russian_and_not_internal_copy() -> None:
    service = ResumeGenerationService()

    profile = SimpleNamespace(
        headline="Prompt Engineering, Data Science, Vibe-coding",
        experiences=[],
    )

    bullets = service._build_summary_bullets(
        profile=profile,
        vacancy_title="Backend Developer",
        selected_skills=["Python", "Git", "LLM"],
        selected_achievements=[
            {
                "title": "Создание ИИ-системы для мониторинга безопасности",
                "fact_status": "needs_confirmation",
                "reason": "ai_relevance",
            }
        ],
        matched_keywords=["Python"],
    )

    joined = "\n".join(bullets)

    assert "Профессиональный фокус" in joined
    assert "Подтверждённые пересечения" in joined
    assert "Дополнительные навыки" in joined
    assert "Проектный опыт" in joined

    assert "Candidate profile aligned" not in joined
    assert "Profile-confirmed" not in joined
    assert "Broader skill base" not in joined
    assert "Relevant project experience" not in joined
    assert "Recent role" not in joined


def test_resume_skill_cleanup_trims_noisy_pdf_layout_fragments() -> None:
    service = ResumeGenerationService()

    skills = service._split_skill_text(
        "Python, Git, Искусственный интеллект, LLM, "
        "Нейросети Прошел 3 стажировки по (промптинг), API, SQL"
    )

    assert skills == [
        "Python",
        "Git",
        "Искусственный интеллект",
        "LLM",
        "Нейросети",
        "API",
        "SQL",
    ]


def test_resume_filters_low_confidence_experience_from_noisy_layout() -> None:
    service = ResumeGenerationService()

    assert service._looks_like_low_confidence_experience_item(
        {
            "company": "(ООО «СГЦ ОПЕКА») 2. Автоматизированный Алтайский Государственный Медицинский ИИ-контроль качества Университет",
            "role": "электромонтер по ремонту и ПВХ оконных изделий обслуживанию электрооборудования по изображениям и",
            "description_raw": "video layout noise",
        }
    )
