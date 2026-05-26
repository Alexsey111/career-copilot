# app\domain\skills\utils.py

from __future__ import annotations

import re

from app.domain.skills.catalog import SKILL_DEFINITIONS


def _normalize_skill_name(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", value.strip().casefold())


def _find_skill(keyword: str):
    normalized_keyword = _normalize_skill_name(keyword)
    return next(
        (
            item
            for item in SKILL_DEFINITIONS
            if _normalize_skill_name(item.canonical_name) == normalized_keyword
        ),
        None,
    )


def extract_keywords(text: str) -> list[str]:
    found: list[str] = []

    for skill in SKILL_DEFINITIONS:
        if any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in skill.patterns
        ):
            found.append(skill.canonical_name)

    return found


def keyword_present(keyword: str, text: str) -> bool:
    skill = _find_skill(keyword)

    if skill is None:
        escaped = re.escape(keyword)
        return bool(
            re.search(
                rf"(?<!\w){escaped}(?!\w)",
                text,
                re.IGNORECASE,
            )
        )

    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in skill.patterns
    )


def get_related_skills(keyword: str) -> list[str]:
    skill = _find_skill(keyword)

    if skill is None:
        return []

    return skill.related_skills
