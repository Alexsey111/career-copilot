#  app\domain\evidence_alignment.py

from __future__ import annotations

import re
from typing import Any


def score_alignment_item(item: dict[str, Any]) -> int:
    score = 0

    requirement = str(item.get("requirement") or "").lower()
    evidence = str(item.get("evidence") or "").lower()
    phrase = f"{requirement} {evidence}"

    if str(item.get("confidence") or "").strip().lower() == "high":
        score += 30

    if any(
        marker in phrase
        for marker in ("pytest", "автотест", "автоматическ", "тестирован")
    ):
        score += 40

    if any(
        marker in phrase
        for marker in ("ci/cd", "gitlab ci", "pipeline", "пайплайн")
    ):
        score += 30

    if any(marker in phrase for marker in ("api", "rest")):
        score += 15

    if any(marker in phrase for marker in ("fastapi", "backend")):
        score += 10

    if any(marker in phrase for marker in ("postgres", "postgresql", "sqlalchemy")):
        score += 8

    if any(marker in phrase for marker in ("docker", "container", "контейнер")):
        score += 8

    return score


def polish_summary_evidence_phrase(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return cleaned

    rules = (
        (
            r"^время ответа api(\s+на\s+\d+%)?$",
            "оптимизации времени ответа API",
        ),
        (
            r"^разработка rest api(?: на fastapi)?$",
            "разработки REST API на FastAPI",
        ),
        (
            r"^настройка ci/cd$",
            "настройки CI/CD",
        ),
        (
            r"^настроил автоматическое тестирование$",
            "настройки автоматического тестирования",
        ),
        (
            r"^настроила автоматическое тестирование$",
            "настройки автоматического тестирования",
        ),
        (
            r"^настройк[аи] автоматического тестирования(?:\s+на\s+pytest)?$",
            "настройки автоматического тестирования",
        ),
        (
            r"^автоматическ[а-я\s]*тестирован[а-я\s]*$",
            "настройки автоматического тестирования",
        ),
        (
            r"^автоматическое тестирование(?:\s+на\s+pytest)?$",
            "настройки автоматического тестирования",
        ),
        (
            r"^интеграция postgresql$",
            "интеграции PostgreSQL",
        ),
        (
            r"^контейнеризац[а-я\s]*$",
            "контейнеризации",
        ),
        (
            r"^python-разработка$",
            "Python-разработки",
        ),
        (
            r"^систем[ау] проектной отчётности$",
            "внедрения системы проектной отчётности",
        ),
    )

    lowered = cleaned.lower()
    for pattern, replacement in rules:
        match = re.match(pattern, lowered, flags=re.IGNORECASE)
        if match:
            suffix = match.group(1) if match.lastindex else ""
            return f"{replacement}{suffix or ''}"

    return cleaned
