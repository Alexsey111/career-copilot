# tests/test_resume_renderer_factuality.py

"""Этап 6 — инлайн-маркировка «неподтверждено» в ATS-тексте резюме."""

from __future__ import annotations

from app.services.resume_renderer import render_resume


def _content_with_achievements(achievements: list[dict]) -> dict:
    return {
        "candidate": {"full_name": "Иван Иванов", "contacts": {}},
        "target_vacancy": {"title": "Python Developer"},
        "sections": {
            "vacancy_aligned_summary": None,
            "skills": [],
            "experience": [],
            "education": [],
            "courses": [],
            "internships": [],
            "project_sections": [],
            "selected_achievements": achievements,
        },
    }


def test_renderer_marks_unconfirmed_achievement() -> None:
    content = _content_with_achievements(
        [
            {
                "title": "Проект X",
                "result": "Рост 30%",
                "fact_status": "needs_confirmation",
            }
        ]
    )

    rendered = render_resume(content)

    assert "- Проект X — Рост 30% (неподтверждено)" in rendered


def test_renderer_no_marker_for_confirmed() -> None:
    content = _content_with_achievements(
        [
            {
                "title": "Проект X",
                "result": "Рост 30%",
                "fact_status": "confirmed",
            }
        ]
    )

    rendered = render_resume(content)

    assert "- Проект X — Рост 30%" in rendered
    assert "(неподтверждено)" not in rendered


def test_renderer_no_marker_for_user_provided() -> None:
    content = _content_with_achievements(
        [
            {
                "title": "Проект X",
                "result": "Рост 30%",
                "fact_status": "user_provided",
            }
        ]
    )

    rendered = render_resume(content)

    assert "(неподтверждено)" not in rendered


def test_renderer_needs_confirmation_literal_absent() -> None:
    content = _content_with_achievements(
        [
            {
                "title": "Проект X",
                "result": "Рост 30%",
                "fact_status": "needs_confirmation",
            }
        ]
    )

    rendered = render_resume(content)

    assert "needs_confirmation" not in rendered
    assert "fact_status" not in rendered


def test_renderer_marks_inferred_achievement() -> None:
    content = _content_with_achievements(
        [
            {
                "title": "Проект Y",
                "narrative": "Спроектировал API",
                "metric_text": "в 3 раза быстрее",
                "fact_status": "inferred",
            }
        ]
    )

    rendered = render_resume(content)

    assert "(неподтверждено)" in rendered
    assert "needs_confirmation" not in rendered