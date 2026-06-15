from __future__ import annotations

import re


INTERNAL_EVIDENCE_LABEL_MARKERS = (
    "signals",
    "implementation signals",
    "backend/api implementation",
    "workflow automation",
    "automation tooling",
    "automation workflow evidence",
    "backend workflow evidence",
)


def clean_vacancy_title(title: str | None) -> str:
    cleaned = str(title or "").strip()

    cleaned = re.sub(
        r"^\s*вакансия\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s+вакансия\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return re.sub(r"\s+", " ", cleaned).strip()


def make_user_facing_evidence_phrase(value: str | None) -> str | None:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if any(marker.lower() in lowered for marker in INTERNAL_EVIDENCE_LABEL_MARKERS):
        return None

    return cleaned


def dedupe_subsumed_phrases(phrases: list[str]) -> list[str]:
    normalized = [
        re.sub(r"\s+", " ", str(phrase or "")).strip(" .;-–—•")
        for phrase in phrases
        if str(phrase or "").strip()
    ]
    normalized = [phrase for phrase in normalized if phrase]

    result: list[str] = []
    for phrase in normalized:
        phrase_lower = phrase.lower()
        if any(
            phrase_lower != other.lower() and phrase_lower in other.lower()
            for other in normalized
        ):
            continue
        result.append(phrase)

    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in result:
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(phrase)
    return deduped


def humanize_vacancy_requirement_phrase(value: str | None) -> str | None:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return None

    lowered = cleaned.lower()
    phrase_map = (
        (
            ("pytest", "testing", "test"),
            "настройка автоматического тестирования",
        ),
        (
            ("fastapi", "backend", "api"),
            "разработка REST API",
        ),
        (
            ("docker", "container", "контейнер"),
            "контейнеризация",
        ),
        (
            ("cicd", "ci/cd", "ci cd", "pipeline"),
            "настройка CI/CD",
        ),
        (
            ("postgres", "postgresql", "sqlalchemy"),
            "интеграция PostgreSQL",
        ),
        (
            ("git", "version control", "repository"),
            "Git",
        ),
        (
            ("workflow automation", "automation", "workflow", "no-code", "nocode"),
            "автоматизация workflow",
        ),
        (
            ("python",),
            "Python-разработка",
        ),
    )

    for markers, phrase in phrase_map:
        if any(marker in lowered for marker in markers):
            return phrase

    return cleaned
