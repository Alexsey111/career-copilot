from __future__ import annotations

from enum import Enum
import re
from typing import Any

from app.services.text_polish.humanizer import (
    lowercase_sentence_start,
)


ACHIEVEMENT_NOMINALIZATION_MAP = (
    (r"^(внедрил|внедрила|внедрил)\b", "внедрение"),
    (r"^(сократил|сократила)\b", "сокращение"),
    (r"^(оптимизировал|оптимизировала)\b", "оптимизация"),
    (r"^(автоматизировал|автоматизировала)\b", "автоматизация"),
    (r"^(реализовал|реализовала)\b", "реализация"),
    (r"^(разработал|разработала)\b", "разработка"),
    (r"^(создал|создала)\b", "создание"),
    (r"^(улучшил|улучшила)\b", "улучшение"),
    (r"^(снизил|снизила)\b", "снижение"),
    (r"^(увеличил|увеличила)\b", "увеличение"),
    (r"^(настроил|настроила)\b", "настройка"),
    (r"^(построил|построила)\b", "построение"),
    (r"^(подготовил|подготовила)\b", "подготовка"),
    (r"^(провёл|провел|провела)\b", "проведение"),
    (r"^(проводил|проводила)\b", "проведение"),
    (r"^(вёл|вел|вела)\b", "ведение"),
    (r"^(управлял|управляла)\b", "управление"),
    (r"^(координировал|координировала)\b", "координация"),
    (r"^(организовал|организовала)\b", "организация"),
    (r"^(сопровождал|сопровождала)\b", "сопровождение"),
    (r"^(устранением)\b", "устранение"),
)

ACHIEVEMENT_NOMINAL_TAIL_REPLACEMENTS = (
    (r"\bсистему\b", "системы"),
    (r"\bсроки\b", "сроков"),
    (r"\bпроцесс\b", "процесса"),
    (r"\bколичество\b", "количества"),
    (r"\bзатраты\b", "затрат"),
    (r"\bостатки\b", "остатков"),
    (r"\bскладские\b", "складских"),
    (r"\bдоговоры\b", "договоров"),
    (r"\bошибки\b", "ошибок"),
    (r"\bсогласования\b", "согласования"),
    (r"\bчек-лист\b", "чек-листа"),
    (r"\bновый\b", "нового"),
    (r"\bфирменный\b", "фирменного"),
    (r"\bстиль\b", "стиля"),
)


class AchievementStyle(str, Enum):
    ACTION = "action"
    NARRATIVE = "narrative"


def cover_letter_result_value(*, selected_achievements: list[dict]) -> str:
    results: list[str] = []
    for item in selected_achievements:
        status = str(item.get("fact_status") or "").strip().lower()
        if status and status not in {"confirmed", "user_provided"}:
            continue
        title = " ".join(str(item.get("title") or "").strip(" .;-–—•").split())
        if not title:
            continue
        results.append(verbalize_achievement_phrase(title, style=AchievementStyle.NARRATIVE))

    results = _dedupe_preserve_order(results)
    if not results:
        return ""
    if len(results) == 1:
        return results[0]
    if len(results) == 2:
        return f"{results[0]} и {results[1]}"
    return f"{', '.join(results[:2])} и {results[2]}"


def build_resume_achievement_sentence(
    selected_achievements: list[dict[str, Any]],
    *,
    role: str = "",
) -> str | None:
    achievement_titles = [
        str(item.get("title") or "").strip()
        for item in selected_achievements[:3]
        if str(item.get("title") or "").strip()
    ]
    if not achievement_titles:
        return None

    first = verbalize_achievement_phrase(achievement_titles[0], style=AchievementStyle.ACTION)
    if len(achievement_titles) == 1:
        return f"За время работы {first}."

    other = "; ".join(
        verbalize_achievement_phrase(title, style=AchievementStyle.ACTION)
        for title in achievement_titles[1:]
        if title
    )
    if not other:
        return f"За время работы {first}."
    return f"За время работы {first}; также {other}."


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = " ".join(str(value or "").split()).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def nounize_achievement_phrase(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return ""

    cleaned = _strip_role_preface(cleaned)
    parts = [
        part.strip()
        for part in re.split(r"\s+и\s+", cleaned)
        if part.strip()
    ]
    if len(parts) > 1:
        return " и ".join(_nounize_achievement_clause(part) for part in parts)

    return _nounize_achievement_clause(cleaned)


def actionize_achievement_phrase(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return ""

    cleaned = _strip_role_subject_preface(cleaned)
    return lowercase_sentence_start(cleaned)


def verbalize_achievement_phrase(
    value: str,
    *,
    style: AchievementStyle = AchievementStyle.ACTION,
) -> str:
    if style == AchievementStyle.NARRATIVE:
        return nounize_achievement_phrase(value)
    return actionize_achievement_phrase(value)


def _strip_role_preface(value: str) -> str:
    text = re.sub(r"^\s*(?:[А-Яа-яЁё-]+\s+){0,4}я\s+занимал(?:ся|ась)\s+", "", value, flags=re.IGNORECASE)
    text = re.sub(r"^\s*я\s+занимал(?:ся|ась)\s+", "", text, flags=re.IGNORECASE)
    return text.strip()


def _strip_role_subject_preface(value: str) -> str:
    text = re.sub(r"^\s*(?:[А-Яа-яЁё-]+\s+){0,4}я\s+", "", value, flags=re.IGNORECASE)
    text = re.sub(r"^\s*я\s+", "", text, flags=re.IGNORECASE)
    return text.strip()


def _nounize_achievement_clause(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not cleaned:
        return ""

    lowered = cleaned.casefold()
    for pattern, replacement in ACHIEVEMENT_NOMINALIZATION_MAP:
        match = re.match(pattern, lowered)
        if not match:
            continue
        tail = cleaned[match.end():].strip(" .;-–—•")
        if not tail:
            return replacement
        tail = _normalize_nominal_tail(tail)
        return f"{replacement} {tail}"

    return lowercase_sentence_start(cleaned)


def _normalize_nominal_tail(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
    if not text:
        return ""

    for source, target in ACHIEVEMENT_NOMINAL_TAIL_REPLACEMENTS:
        text = re.sub(source, target, text, flags=re.IGNORECASE)

    return text


class AchievementVerbalizer:
    def cover_letter_result_value(
        self,
        *,
        selected_achievements: list[dict],
    ) -> str:
        return cover_letter_result_value(
            selected_achievements=selected_achievements,
        )

    def build_resume_achievement_sentence(
        self,
        selected_achievements: list[dict[str, Any]],
        *,
        role: str = "",
    ) -> str | None:
        return build_resume_achievement_sentence(
            selected_achievements,
            role=role,
        )

    def nounize_achievement_phrase(self, value: str) -> str:
        return nounize_achievement_phrase(value)

    def actionize_achievement_phrase(self, value: str) -> str:
        return actionize_achievement_phrase(value)

    def verbalize_achievement_phrase(
        self,
        value: str,
        *,
        style: AchievementStyle = AchievementStyle.ACTION,
    ) -> str:
        return verbalize_achievement_phrase(value, style=style)

    def achievement_result_sentence(self, achievements: list[str]) -> str:
        nounized = [
            verbalize_achievement_phrase(value, style=AchievementStyle.NARRATIVE)
            for value in achievements
            if str(value or "").strip()
        ]
        nounized = _dedupe_preserve_order([item for item in nounized if item])
        if not nounized:
            return "Практический результат моей работы —"
        if len(nounized) == 1:
            return f"Практический результат моей работы — {nounized[0]}."
        return f"Практический результат моей работы — {nounized[0]}; {nounized[1]}."
