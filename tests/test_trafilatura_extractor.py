from __future__ import annotations

from pathlib import Path
import asyncio
from types import SimpleNamespace

import pytest

from app.services.vacancy_text_extractors.trafilatura_extractor import (
    TrafilaturaVacancyExtractor,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "vacancy_html"


@pytest.mark.parametrize(
    "fixture_name, expected_title, expected_fragments, forbidden_fragments",
    [
        (
            "hh_vacancy.html",
            "Python Backend Developer - HH Example",
            [
                "Python Backend Developer",
                "Требования",
                "FastAPI",
                "PostgreSQL",
                "Разрабатывать backend API",
            ],
            [
                "cookie",
                "Главная",
                "Вакансии",
                "Политика конфиденциальности",
            ],
        ),
        (
            "linkedin_vacancy.html",
            "Senior Backend Engineer | LinkedIn Jobs",
            [
                "Responsibilities",
                "Python services",
                "SQLAlchemy",
                "RAG pipelines",
            ],
            [
                "Accept cookies",
                "Home",
                "Messaging",
                "Privacy Policy",
            ],
        ),
        (
            "careers_page.html",
            "Careers at Example AI",
            [
                "What you'll do",
                "Build Python backend services",
                "FastAPI",
                "SQLAlchemy",
                "prompt engineering",
            ],
            [
                "cookies",
                "Careers",
                "Blog",
                "Privacy",
                "Terms",
            ],
        ),
    ],
)
def test_trafilatura_extractor_smoke_on_representative_vacancy_pages(
    fixture_name: str,
    expected_title: str,
    expected_fragments: list[str],
    forbidden_fragments: list[str],
) -> None:
    extractor = TrafilaturaVacancyExtractor()
    html = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")

    result = asyncio.run(
        extractor.extract(url="https://example.com/vacancy", html=html)
    )

    assert result.title == expected_title
    assert len(result.text.splitlines()) >= 4

    for fragment in expected_fragments:
        assert fragment in result.text

    for fragment in forbidden_fragments:
        assert fragment.lower() not in result.text.lower()


def test_trafilatura_extractor_falls_back_to_dom_text_when_primary_extraction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = TrafilaturaVacancyExtractor()
    html = """
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <title>Fallback Vacancy</title>
    <script>window.__DATA__ = "should not leak";</script>
    <style>body { display: none; }</style>
  </head>
  <body>
    <noscript>Enable JavaScript</noscript>
    <nav>Home | Jobs | About</nav>
    <main>
      <h1>Senior Python Engineer</h1>
      <p>Python, FastAPI, PostgreSQL, Docker.</p>
    </main>
  </body>
</html>
"""

    monkeypatch.setattr(
        "app.services.vacancy_text_extractors.trafilatura_extractor.trafilatura",
        SimpleNamespace(extract=lambda *args, **kwargs: None),
    )

    result = asyncio.run(
        extractor.extract(url="https://example.com/fallback", html=html)
    )

    assert result.title == "Fallback Vacancy"
    assert "Senior Python Engineer" in result.text
    assert "Python, FastAPI, PostgreSQL, Docker." in result.text
    assert "should not leak" not in result.text
    assert "Enable JavaScript" not in result.text
    assert "Home" not in result.text
    assert "Jobs" not in result.text
    assert "About" not in result.text


def test_trafilatura_extractor_returns_rich_contract() -> None:
    extractor = TrafilaturaVacancyExtractor()
    html = """
<!doctype html>
<html lang="en">
  <head>
    <title>Sample Vacancy</title>
  </head>
  <body>
    <main>
      <h1>Python Engineer</h1>
      <p>FastAPI, PostgreSQL, Docker.</p>
    </main>
  </body>
</html>
"""

    result = asyncio.run(
        extractor.extract(url="https://example.com/sample", html=html)
    )

    assert result.extractor == "trafilatura"
    assert result.extraction_method in {"trafilatura", "fallback_dom"}
    assert result.content_length == len(result.text)
    assert result.success is True
