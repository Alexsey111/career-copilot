# app/domain/vacancy_title_extractor.py

from __future__ import annotations

import re


SKIP_PATTERNS = [
    r"уровень\s+доход",
    r"зарплат",
    r"опыт\s+работ",
    r"полная\s+занят",
    r"частичная\s+занят",
    r"проектная\s+работ",
    r"стажиров",
    r"график",
    r"рабочих\s+час",
    r"рабочий\s+час",
    r"формат\s+работ",
    r"оформлени",
    r"выплат",
    r"сейчас\s+эту",
    r"просматр",
    r"отзыв",
    r"напишите\s+телефон",
    r"нажимая",
    r"компания\s+\w",
    r"аккредитация",
    r"ит-компания",
    r"\d+\s+отзыв",
    r"^\s*описание\s*$",
    r"^в[ао]с\s+пригласил",
    r"^кто\s+мы",
    r"^чем\s+предстоит",
    r"looking\s+at",
    r"people\s+are",
    r"contract\s+type",
    r"employment\s+type",
    r"work\s+schedule",
    r"salary",
]

HEADING_PATTERNS = [
    r"(?:мы|они)\s+ищ[емут]+\s+((?:\w+-)?\w+(?:\s+\w+){0,3})",
    r"(?:we\s+are\s+)?(?:looking\s+for|hiring)\s+(?:a\s+)?(.+?)(?:\s+with|\s+who|\s+for|$)",
    r"ваканси[яю]\s*[«\"]?(.+?)[»\"]?(?:\s*[-—–]\s*|\s*$)",
    r"(?:должность|позиция|роль)\s*[:\-]\s*(.+)",
]

TITLE_CLEANUP = [
    (r"^мы\s+ищем\s+", ""),
    (r"^они\s+ищут?\s+", ""),
    (r"^ваканси[яю]\s+", ""),
    (r"^должность\s*[:\-]\s*", ""),
    (r"^позиция\s*[:\-]\s*", ""),
    (r"^роль\s*[:\-]\s*", ""),
]


def extract_vacancy_title(text: str, fallback: str = "") -> str:
    lines = text.split("\n")

    for line in lines[:30]:
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue

        lower = stripped.lower()
        if any(re.search(p, lower) for p in SKIP_PATTERNS):
            continue

        if re.match(r"^[\d\s\-–,\.]+$", stripped):
            continue

        for pattern in HEADING_PATTERNS:
            match = re.search(pattern, stripped, re.IGNORECASE)
            if match:
                title = match.group(1).strip() if match.lastindex else match.group(0).strip()
                return _clean_title(title)

        if _is_likely_title(stripped):
            return _clean_title(stripped)

    return fallback


def _is_likely_title(text: str) -> bool:
    if len(text) > 120:
        return False
    if text.count("\n") > 0:
        return False

    lower = text.lower()
    if any(x in lower for x in ["обязанности", "требования", "условия", "опыт работы"]):
        return False

    words = text.split()
    if len(words) > 8:
        return False

    return True


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"[:：\-—–]+$", "", cleaned).strip()

    for pattern, replacement in TITLE_CLEANUP:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    words = cleaned.split()
    if len(words) <= 3:
        cleaned = cleaned.title()
    else:
        cleaned = " ".join(words[:1]) + " " + " ".join(words[1:]).lower()

    return cleaned.strip()
