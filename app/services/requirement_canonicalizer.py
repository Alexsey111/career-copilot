from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.requirement_normalization import (
    classify_requirement_phrase,
    normalize_requirement_phrase,
)


@dataclass(slots=True, frozen=True)
class CanonicalRequirement:
    raw: str
    normalized: str
    display: str
    question_label: str
    summary_label: str
    confidence_label: str
    category: str
    is_noise: bool


HEADER_WORDS = {
    "требования",
    "требование",
    "обязанности",
    "условия",
    "навыки",
    "умения",
    "образование",
    "опыт",
    "желательно",
    "что нужно",
    "что мы ждем",
    "что мы ждём",
    "будет плюсом",
    "будет преимуществом",
    "преимуществом будет",
}

NOISE_WORDS = {
    "что",
    "высшее",
    "среднее",
    "образование",
    "опыт",
    "опыт работы",
    "опыт работы от 1 года",
}

CONNECTOR_WORDS = {
    "и",
    "в",
    "на",
    "по",
    "или",
    "а также",
}

SOFT_SKILL_PREFIXES = (
    "коммуникабель",
    "вниматель",
    "ответствен",
    "исполнитель",
    "обучаем",
    "стрессоустойчив",
    "аккурат",
    "доброжелатель",
    "скорост",
    "компетент",
    "инициатив",
    "пунктуаль",
)

PROTECTED_REQUIREMENT_PATTERNS = (
    r'ООО\s+"[^"]+"',
    r"C\+\+",
    r"C#",
    r"Node\.js",
    r"ASP\.NET",
)

CANONICAL_DISPLAY = {
    "python": "Python",
    "c#": "C#",
    "c++": "C++",
    "node.js": "Node.js",
    "asp.net": "ASP.NET",
    "fastapi": "FastAPI",
    "postgresql": "PostgreSQL",
    "docker": "Docker",
    "rest api": "REST API",
    "wms": "WMS",
    "тсд": "ТСД",
    "мис": "МИС",
    "эмк": "ЭМК",
    "figma": "Figma",
    "photoshop": "Photoshop",
    "illustrator": "Illustrator",
    "fmcg": "FMCG",
    "1с": "1С",
    "1с 8.3": "1С 8.3",
    "знание профильного законодательства": "Знание профильного законодательства",
    "управление полевой командой": "Управление полевой командой",
    "полевой аудит торговых точек": "Полевой аудит торговых точек",
    "розничные продажи": "Розничные продажи",
    "мерчандайзинг": "Мерчандайзинг",
}


def split_atomic_requirements(value: str) -> list[str]:
    cleaned = _clean_text(value)
    if not cleaned:
        return []

    protected_text, placeholders = _protect_tokens(cleaned)
    # Сплитим по явным разделителям пунктов: ; | / • и запятой. Запятая нужна
    # для легитимных списков («Python, FastAPI, PostgreSQL» → 3 пункта, каждое
    # со своим coverage в fit). Но запятая внутри фразы-предложения («работа
    # с инструментами, связанными с сервисами») давала обрубок «Связанных с
    # сервисами» как отдельное требование — это продолжение фразы, не пункт.
    # Поэтому после сплита склеиваем обратно обрубки, начинающиеся с
    # предлога/союза/причастия (FRAGMENT_START_WORDS).
    protected_text = re.sub(r"\s*[;|/•]\s*", "@@REQSEP@@", protected_text)

    parts: list[str] = []
    for chunk in protected_text.split("@@REQSEP@@"):
        if not _clean_text(chunk):
            continue
        sub = [
            _restore_tokens(s, placeholders)
            for s in re.split(r"\s*,\s*", chunk)
            if _clean_text(s)
        ]
        # Склейка обрубков-продолжений к предыдущему пункту.
        merged: list[str] = []
        for s in sub:
            if merged and _is_continuation_fragment(s):
                merged[-1] = f"{merged[-1]}, {s}"
            else:
                merged.append(s)
        parts.extend(merged)

    return _dedupe_preserve_order(parts or [cleaned])


# Обрубки, начинающиеся с этих слов — продолжение предыдущей фразы, не новый
# пункт. Предлоги/союзы и причастия/деепричастия, которые в русском открывают
# уточнение («связанных с сервисами», «и Формами», «в работе будут»). Общая
# лингвистическая эвристика, не хардкод под конкретное резюме.
FRAGMENT_START_WORDS = {
    "с", "со", "в", "во", "на", "по", "при", "или", "для", "от", "до", "из",
    "а", "но", "что", "как", "так", "через", "над", "под", "об", "о", "к",
    "и", "из-за", "без", "кроме", "среди", "между", "перед", "про",
    "связанных", "связанные", "связанная", "связанными", "связан", "связано",
    "включая", "используя", "используемых", "применяемых", "включающих",
    "содержащих", "относящихся", "касающихся", "влияющих", "позволяющих",
    "обеспечивающих", "участвующих", "применяющих", "имеющих", "входящих",
    "выполняемых", "проводимых", "охватывающих", "затрагивающих",
}

# Косвенные падежные окончания первого слова обрубка (творит./родит./дат./
# предл.), указывающие на продолжение перечисления однородных членов:
# «связанных с сервисами, автоматизацией», «работы ботов, форм, сервисов»,
# «доступами, сервисами и настройками». Именительный падеж сюда не входит —
# он открывает самостоятельный пункт («разработка», «выполнение»).
_KOSVENNYY_ENDINGS = (
    "ами", "ями", "ой", "ей", "ею", "ью",            # творит.
    "ов", "ев", "ей", "ий", "ям", "ам", "ах", "ях",   # родит./дат./предл.
    "ым", "им", "ыми", "ими", "ого", "его", "ому", "ему", "ых", "их",  # прилаг.
)

# Именительные окончания — обрубок с таким окончанием первого слова —
# самостоятельный пункт (субъект/навык/действие), не продолжение.
_IMENITELNYY_ENDINGS = ("а", "я", "о", "е", "ы", "и", "ь")


def _is_tech_token(word: str) -> bool:
    """Латиница/цифры/tech-символы — tech-термин, всегда самостоятельный пункт."""
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._+\-#]*", word))


def _is_cyrillic(word: str) -> bool:
    return bool(re.fullmatch(r"[а-яё]+", word, flags=re.UNICODE))


def _is_continuation_fragment(value: str) -> bool:
    cleaned = _clean_text(value)
    if not cleaned:
        return False
    # Сохраняем исходный регистр первого слова — имена собственные/продукты
    # («Контур», «Битрикс») пишутся с заглавной и НЕ являются обрубками.
    orig_words = re.split(r"\s+", cleaned)
    first_orig = orig_words[0]
    first = first_orig.lower()

    if first in FRAGMENT_START_WORDS:
        return True
    if _is_tech_token(first):
        return False
    # Косвенный падеж первого слова (>=4 букв) → продолжение перечисления.
    if len(first) >= 4 and any(first.endswith(e) for e in _KOSVENNYY_ENDINGS):
        return True
    # 1-словный нарицательный обрубок с нулевым/согласным окончанием, не
    # именительный («форм», «таблиц», «ссылок») — род. падеж ж.р., продолжение
    # перечисления («работы ботов, форм, таблиц»). Имена собственные (первая
    # буква заглавная) — самостоятельные пункты, не склеиваются.
    if (
        len(orig_words) == 1
        and _is_cyrillic(first)
        and len(first) >= 3
        and not any(first.endswith(e) for e in _IMENITELNYY_ENDINGS)
        and not first_orig[:1].isupper()
    ):
        return True
    return False


def canonicalize_requirement(value: str) -> CanonicalRequirement:
    raw = str(value or "")
    cleaned = _strip_requirement_prefix(_clean_text(raw))
    normalized = _normalized_text(cleaned)
    category = _classify_requirement(cleaned)
    display = _display_requirement(cleaned)
    question_label = _question_label(display, category)
    summary_label = _summary_label(display, category)
    confidence_label = _confidence_label(display)
    is_noise = _is_noise(cleaned, normalized, category)

    return CanonicalRequirement(
        raw=raw,
        normalized=normalized,
        display=display,
        question_label=question_label,
        summary_label=summary_label,
        confidence_label=confidence_label,
        category=category,
        is_noise=is_noise,
    )


def canonicalize_requirements(values: list[str]) -> list[CanonicalRequirement]:
    result: list[CanonicalRequirement] = []
    seen: set[str] = set()

    for value in values:
        canonical = canonicalize_requirement(value)
        key = canonical.normalized
        if canonical.is_noise or not key or key in seen:
            continue
        seen.add(key)
        result.append(canonical)

    return result


def requirement_is_user_facing_learning_topic(value: str) -> bool:
    canonical = canonicalize_requirement(value)
    return not canonical.is_noise and canonical.category not in {
        "education",
        "certification",
        "experience",
        "behavioral",
    }


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")


def _protect_tokens(value: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}
    protected_text = value

    for index, pattern in enumerate(PROTECTED_REQUIREMENT_PATTERNS):
        for match in re.finditer(pattern, protected_text, flags=re.IGNORECASE):
            placeholder = f"__REQ_TOKEN_{index}_{len(placeholders)}__"
            placeholders[placeholder] = match.group(0)
            protected_text = protected_text.replace(match.group(0), placeholder)

    return protected_text, placeholders


def _restore_tokens(value: str, placeholders: dict[str, str]) -> str:
    restored = value
    for placeholder, original in placeholders.items():
        restored = restored.replace(placeholder, original)
    return restored


def _strip_requirement_prefix(value: str) -> str:
    header_pattern = "|".join(re.escape(word) for word in sorted(HEADER_WORDS, key=len, reverse=True))
    return re.sub(
        rf"^(?:{header_pattern})\s*[:\-–—]\s*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip(" .;-–—•")


def _normalized_text(value: str) -> str:
    normalized = normalize_requirement_phrase(value)
    return _clean_text(normalized).casefold()


def _display_requirement(value: str) -> str:
    cleaned = _clean_text(value)
    lowered = cleaned.casefold()
    normalized = _normalized_text(cleaned)

    if not cleaned:
        return ""

    if lowered in CANONICAL_DISPLAY:
        return CANONICAL_DISPLAY[lowered]

    if normalized in CANONICAL_DISPLAY:
        return CANONICAL_DISPLAY[normalized]

    if restored := _project_display(cleaned):
        return restored

    normalized_display = normalize_requirement_phrase(cleaned)
    if normalized_display:
        cleaned = _clean_text(normalized_display)

    if cleaned.startswith('ООО "'):
        return cleaned

    return cleaned[:1].upper() + cleaned[1:]


def _project_display(value: str) -> str:
    lowered = value.casefold()
    if "коммерческ" in lowered and ("промышлен" in lowered or "объект" in lowered):
        return "Коммерческие проекты"
    if "жил" in lowered and "объект" in lowered:
        return "Жилые проекты"
    return ""


def _question_label(display: str, category: str) -> str:
    lowered = display.casefold()
    if lowered == "коммерческие проекты":
        return "опыт управления коммерческими проектами"
    if lowered == "жилые проекты":
        return "опыт управления жилыми проектами"
    if category == "skill":
        return display
    return display[:1].lower() + display[1:] if display else ""


def _summary_label(display: str, category: str) -> str:
    lowered = display.casefold()
    if lowered in {"коммерческие проекты", "жилые проекты"}:
        return ""
    if category in {"education", "certification", "experience", "behavioral"}:
        return ""
    return display


def _confidence_label(display: str) -> str:
    lowered = display.casefold()
    if lowered == "коммерческие проекты":
        return "Опыт управления коммерческими проектами"
    if lowered == "жилые проекты":
        return "Опыт управления жилыми проектами"
    return display


def _classify_requirement(value: str) -> str:
    lowered = value.casefold()
    soft_marker_count = sum(marker in lowered for marker in SOFT_SKILL_PREFIXES)
    if soft_marker_count >= 2:
        return "behavioral"
    if lowered in {"опыт", "опыт работы", "опыт работы от 1 года"}:
        return "experience"
    if "опыт работы" in lowered and any(char.isdigit() for char in lowered):
        return "experience"
    return classify_requirement_phrase(value)


def _is_noise(value: str, normalized: str, category: str) -> bool:
    cleaned = _clean_text(value)
    lowered = cleaned.casefold()

    if not cleaned:
        return True

    if len(cleaned) < 3 and not re.search(r"\d", cleaned):
        return True

    if lowered in HEADER_WORDS or lowered in NOISE_WORDS or lowered in CONNECTOR_WORDS:
        return True

    if len(cleaned.split()) == 1 and lowered.endswith(("ыми", "ими")):
        return True

    if category in {"education", "certification"} and lowered in NOISE_WORDS:
        return True

    if not normalized:
        return True

    return False


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _clean_text(value)
        key = cleaned.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)

    return result
