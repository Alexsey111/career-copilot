# tests/test_resume_renderer_localization.py

"""Этап 7 — локализация заголовков секций резюме по рынку (RU/EU/US)."""

from __future__ import annotations

from app.services.resume_renderer import render_resume


def _full_content() -> dict:
    return {
        "candidate": {
            "full_name": "Иван Иванов",
            "headline": "Backend Developer",
            "location": "Москва",
            "contacts": {"email": "ivan@example.com", "phone": "+7 900 000 0000"},
        },
        "target_vacancy": {"title": "Python Developer"},
        "sections": {
            "vacancy_aligned_summary": "Краткое резюме кандидата.",
            "skills": ["Python", "FastAPI"],
            "experience": [
                {"role": "Backend", "company": "Acme", "period": "2020-2024", "description_raw": None}
            ],
            "education": [{"institution": "Университет", "degree": "BSc", "period": "2016-2020"}],
            "courses": [{"provider": "Coursera", "title": "ML", "year": "2021"}],
            "internships": [{"title": "Intern", "organization": "Yandex", "period": "2019"}],
            "project_sections": [],
            "selected_achievements": [
                {
                    "title": "Проект X",
                    "narrative": "Спроектировал API",
                    "metric_text": "в 3 раза быстрее",
                    "fact_status": "needs_confirmation",
                }
            ],
        },
    }


def test_render_ru_default_headings() -> None:
    rendered = render_resume(_full_content())

    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in rendered
    assert "КРАТКОЕ РЕЗЮМЕ" in rendered
    assert "КЛЮЧЕВЫЕ НАВЫКИ" in rendered
    assert "ОПЫТ РАБОТЫ" in rendered
    assert "ОБРАЗОВАНИЕ" in rendered
    assert "КУРСЫ" in rendered
    assert "СТАЖИРОВКИ / УЧЕБНЫЕ ПРОЕКТЫ" in rendered
    assert "КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ" in rendered
    assert "(неподтверждено)" in rendered
    assert "Результат:" in rendered
    # Английских заголовков нет при дефолте.
    assert "SUMMARY" not in rendered
    assert "KEY SKILLS" not in rendered


def test_render_us_headings_from_meta() -> None:
    content = _full_content()
    content["meta"] = {"market": "US"}

    rendered = render_resume(content)

    assert "TARGET ROLE" in rendered
    assert "SUMMARY" in rendered
    assert "KEY SKILLS" in rendered
    assert "EXPERIENCE" in rendered
    assert "EDUCATION" in rendered
    assert "COURSES" in rendered
    assert "INTERNSHIPS / ACADEMIC PROJECTS" in rendered
    assert "KEY ACHIEVEMENTS" in rendered
    assert "(unverified)" in rendered
    assert "Result:" in rendered
    # Русских заголовков нет при US.
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" not in rendered
    assert "(неподтверждено)" not in rendered


def test_render_eu_headings_from_root_market() -> None:
    content = _full_content()
    content["market"] = "eu"  # корневой ключ, без meta

    rendered = render_resume(content)

    assert "TARGET ROLE" in rendered
    assert "SUMMARY" in rendered
    assert "KEY ACHIEVEMENTS" in rendered
    assert "(unverified)" in rendered
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" not in rendered


def test_render_explicit_market_arg_overrides_content() -> None:
    content = _full_content()
    content["meta"] = {"market": "ru"}

    rendered = render_resume(content, market="us")

    assert "TARGET ROLE" in rendered
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" not in rendered


def test_render_invalid_market_falls_back_to_ru() -> None:
    content = _full_content()
    content["meta"] = {"market": "XX"}

    rendered = render_resume(content)

    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in rendered
    assert "TARGET ROLE" not in rendered


def test_render_section_order_preserved_us() -> None:
    rendered = render_resume(_full_content(), market="us")

    assert rendered.index("EXPERIENCE") < rendered.index("EDUCATION")
    assert rendered.index("EDUCATION") < rendered.index("COURSES")
    assert rendered.index("COURSES") < rendered.index("INTERNSHIPS / ACADEMIC PROJECTS")
    assert rendered.index("INTERNSHIPS / ACADEMIC PROJECTS") < rendered.index("KEY ACHIEVEMENTS")


def test_render_us_unverified_suffix_for_needs_confirmation() -> None:
    content = _full_content()
    content["meta"] = {"market": "us"}

    rendered = render_resume(content)

    assert "- Проект X — Спроектировал API Result: в 3 раза быстрее (unverified)" in rendered


def test_render_us_confirmed_has_no_suffix() -> None:
    content = _full_content()
    content["meta"] = {"market": "us"}
    content["sections"]["selected_achievements"][0]["fact_status"] = "confirmed"

    rendered = render_resume(content)

    assert "(unverified)" not in rendered