from __future__ import annotations

import re


NORMALIZATION_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "bim",
            "процесс",
        ),
        "BIM-процессы",
    ),
    (
        (
            "экспертиз",
        ),
        "взаимодействие с экспертизой",
    ),
    (
        (
            "проектная документац",
            "проектный менеджмент",
            "ведение проектной документац",
        ),
        "ведение проектной документации",
    ),
    (
        (
            "деловая коммуникация",
            "организаторские навыки",
        ),
        "деловая коммуникация",
    ),
    (
        (
            "команду архитекторов",
            "инженеров",
            "bim-специалистов",
            "управленцев",
        ),
        "управление межфункциональной проектной командой",
    ),
    (
        (
            "проектной bim-компании",
            "реальными задачами",
            "объёмом проектов",
        ),
        "опыт BIM-проектирования",
    ),
)


def normalize_requirement_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" .;-–—•")
    if not cleaned:
        return ""

    lowered = cleaned.casefold()
    for markers, normalized in NORMALIZATION_RULES:
        if all(marker.casefold() in lowered for marker in markers):
            return normalized

    return cleaned


def requirement_match_key(value: str) -> str:
    normalized = normalize_requirement_phrase(value)
    key = re.sub(r"\s+", " ", normalized).strip(" .;-–—•").casefold()

    aliases = {
        "проектная документация": "ведение проектной документации",
        "ведение документации": "ведение проектной документации",
        "ведение проектной документации": "ведение проектной документации",
    }

    return aliases.get(key, key)
