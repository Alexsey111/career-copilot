from types import SimpleNamespace

from app.services.vacancy_analysis_service import (
    NICE_TO_HAVE_START_HEADINGS,
    REQUIREMENT_START_HEADINGS,
    STOP_HEADINGS,
    VacancyAnalysisService,
)


def test_extract_section_items_handles_colon_headings_and_bullets() -> None:
    service = VacancyAnalysisService()

    lines = service._clean_lines(
        """
Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker

Условия:
- Удаленная работа
"""
    )

    must_have = service._extract_section_items(
        lines,
        start_headings=REQUIREMENT_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )
    nice_to_have = service._extract_section_items(
        lines,
        start_headings=NICE_TO_HAVE_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )

    assert must_have == ["Python", "FastAPI", "PostgreSQL"]
    assert nice_to_have == ["Redis", "Docker"]


def test_extract_keywords_detects_common_backend_and_ai_skills() -> None:
    service = VacancyAnalysisService()

    keywords = service._extract_keywords(
        "AI Product Engineer",
        """
Нужен Python backend developer.
Стек: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Docker.
Важно: LLM, RAG, prompt engineering, pytest.
""",
    )

    assert "Python" in keywords
    assert "FastAPI" in keywords
    assert "SQLAlchemy" in keywords
    assert "Alembic" in keywords
    assert "PostgreSQL" in keywords
    assert "Redis" in keywords
    assert "Docker" in keywords
    assert "LLM" in keywords
    assert "RAG" in keywords
    assert "Prompt Engineering" in keywords
    assert "Pytest" in keywords


def test_compare_with_profile_uses_skill_alias_patterns() -> None:
    service = VacancyAnalysisService()

    profile = SimpleNamespace(
        headline="AI Product Engineer",
        summary="Разрабатываю backend на Python и FastAPI.",
        target_roles_json=["AI Product Engineer"],
        experiences=[
            SimpleNamespace(
                company="Acme",
                role="Backend Developer",
                description_raw="Работал с Postgres, Docker и async API.",
            )
        ],
        achievements=[
            SimpleNamespace(
                title="LLM ассистент",
                action="Собрал RAG pipeline.",
                result="Ускорил обработку данных.",
                metric_text=None,
            )
        ],
    )

    strengths, gaps, match_score = service._compare_with_profile(
        profile,
        ["Python", "FastAPI", "PostgreSQL", "Docker", "RAG", "Redis"],
        must_have=["Python", "FastAPI", "PostgreSQL", "Docker", "RAG"],
        nice_to_have=["Redis"],
    )

    strength_keywords = {item["keyword"] for item in strengths}
    gap_keywords = {item["keyword"] for item in gaps}

    assert strength_keywords == {"Python", "FastAPI", "PostgreSQL", "Docker", "RAG"}
    assert gap_keywords == {"Redis"}
    assert match_score == 94


def test_fallback_requirement_candidates_uses_skill_patterns_not_plain_labels() -> None:
    service = VacancyAnalysisService()

    lines = service._clean_lines(
        """
Мы ищем инженера в продуктовую команду.
Работа с Postgres обязательна.
Опыт контейнеризации будет плюсом.
Нужно понимать языковые модели.
"""
    )

    candidates = service._fallback_requirement_candidates(lines)

    assert "Работа с Postgres обязательна." in candidates
    assert "Опыт контейнеризации будет плюсом." in candidates
    assert "Нужно понимать языковые модели." in candidates


def test_scoped_requirement_matching_does_not_create_generic_api_sql_duplicates() -> None:
    service = VacancyAnalysisService()

    must_have = ["Python", "FastAPI", "PostgreSQL"]
    nice_to_have = ["Redis", "Docker"]

    keywords = service._extract_keywords(
        "Backend Developer",
        """
Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker
""",
    )

    assert keywords == ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"]

    requirement_keywords = service._build_requirement_keywords(
        keywords=keywords,
        must_have=must_have,
        nice_to_have=nice_to_have,
    )

    assert [(item.keyword, item.scope) for item in requirement_keywords] == [
        ("Python", "must_have"),
        ("FastAPI", "must_have"),
        ("PostgreSQL", "must_have"),
        ("Redis", "nice_to_have"),
        ("Docker", "nice_to_have"),
    ]


def test_profile_summary_skills_are_used_for_match_score() -> None:
    service = VacancyAnalysisService()

    profile = SimpleNamespace(
        headline="AI Product Engineer",
        summary="Python, SQL, FastAPI, Docker, LLM, Git",
        target_roles_json=["AI Product Engineer"],
        experiences=[],
        achievements=[],
    )

    strengths, gaps, match_score = service._compare_with_profile(
        profile,
        ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
        must_have=["Python", "FastAPI", "PostgreSQL"],
        nice_to_have=["Redis", "Docker"],
    )

    strength_keywords = {item["keyword"] for item in strengths}
    gap_keywords = {item["keyword"] for item in gaps}

    assert strength_keywords == {"Python", "FastAPI", "Docker"}
    assert gap_keywords == {"PostgreSQL", "Redis"}
    assert match_score == 64


def test_extract_section_items_handles_inline_colon_headings() -> None:
    service = VacancyAnalysisService()

    lines = service._clean_lines(
        """
Требования: Python, FastAPI, PostgreSQL
Будет плюсом: Redis, Docker
Условия: Удаленная работа
"""
    )

    must_have = service._extract_section_items(
        lines,
        start_headings=REQUIREMENT_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )
    nice_to_have = service._extract_section_items(
        lines,
        start_headings=NICE_TO_HAVE_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )

    assert must_have == ["Python", "FastAPI", "PostgreSQL"]
    assert nice_to_have == ["Redis", "Docker"]
