from __future__ import annotations

import re
from typing import Literal


RequirementClassification = Literal[
    "education",
    "certification",
    "skill",
    "competency",
]


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
    (
        (
            "опыт работы",
            "данном направлении",
            "не менее 3 лет",
        ),
        "опыт работы сантехником от 3 лет",
    ),
    (
        (
            "инженерными коммуникациями",
        ),
        "обслуживание инженерных систем",
    ),
)


IGNORED_REQUIREMENT_HEADERS = {
    "к квалификации",
    "образование",
    "опыт",
    "профессиональные",
    "навыки",
    "профессиональные навыки",
    "требования",
    "требования к квалификации",
}


def _cleanup_requirement_grammar(value: str) -> str:
    cleaned = value

    legislation_markers = (
        "конституц",
        "устав",
        "кодекс",
        "законодательств",
        "федеральн",
        "нормативн",
        "правов",
    )
    if (
        re.search(r"^знани[ея]\s+", cleaned, flags=re.IGNORECASE)
        and sum(marker in cleaned.casefold() for marker in legislation_markers) >= 2
    ):
        return "знание профильного законодательства"

    phrase_rules: tuple[tuple[str, str], ...] = (
        (
            r".*\bнормотворческ\w+\s+деятельност\w*\b.*",
            "нормотворческая деятельность",
        ),
        (
            r".*\b(?:официально[-\s]?делов\w+)\s+стил\w*\b.*",
            "официально-деловой стиль",
        ),
        (
            r".*\b(?:ведени[ея]|навык\w*)\s+делов\w+\s+переговор\w*\b.*",
            "ведение переговоров",
        ),
        (
            r".*\bработ[аы]\s+с\s+планограмм\w*\b.*",
            "работа с планограммами",
        ),
    )
    for pattern, replacement in phrase_rules:
        if re.match(pattern, cleaned, flags=re.IGNORECASE):
            return replacement

    cleaned = re.sub(
        (
            r"^(?:наличие\s+)?(?:практическ\w+\s+)?"
            r"(?:опыт(?:а)?\s+(?:работы\s+)?с|"
            r"опыт\s+работы\s+с|"
            r"владени[ея]|"
            r"знани[ея]|"
            r"понимани[ея]|"
            r"навык(?:и|ов)?|"
            r"умени[ея]|"
            r"наличие\s+навыков|"
            r"требуется)\s+"
        ),
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" .;-–—•")

    cleaned = re.sub(
        r"^(?:ведения|ведение)\s+делов\w+\s+переговор\w*$",
        "ведение переговоров",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned


def _retail_requirement_phrases(value: str) -> list[str]:
    lowered = value.casefold()
    phrases: list[str] = []

    if "мерчандайз" in lowered or "планограмм" in lowered:
        phrases.append("мерчандайзинг")
    if any(
        marker in lowered
        for marker in ("полев", "торговых точ", "торговые точ", "аудит", "визит")
    ):
        phrases.append("полевой аудит торговых точек")
    if any(marker in lowered for marker in ("команд", "супервайз", "торговых представителей")):
        phrases.append("управление полевой командой")
    if any(marker in lowered for marker in ("рознич", "ритейл", "retail", "продаж")):
        phrases.append("розничные продажи")
    if "fmcg" in lowered:
        phrases.append("FMCG")

    return _dedupe_preserve_order(phrases)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        key = cleaned.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def normalize_requirement_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" .;-–—•")
    if not cleaned:
        return ""

    lowered = cleaned.casefold()
    for markers, normalized in NORMALIZATION_RULES:
        if all(marker.casefold() in lowered for marker in markers):
            return normalized

    retail_phrases = _retail_requirement_phrases(cleaned)
    if retail_phrases:
        return retail_phrases[0]

    return _cleanup_requirement_grammar(cleaned)


def normalize_requirement_phrases(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" .;-–—•")
    if not cleaned:
        return []

    lowered = cleaned.casefold()
    personal_traits = _personal_trait_requirement_phrases(cleaned)
    if personal_traits:
        return personal_traits

    if not any(
        all(marker.casefold() in lowered for marker in markers)
        for markers, _ in NORMALIZATION_RULES
    ):
        retail_phrases = _retail_requirement_phrases(cleaned)
        if retail_phrases:
            return retail_phrases

    normalized = normalize_requirement_phrase(cleaned)
    return [normalized] if normalized else []


def _personal_trait_requirement_phrases(value: str) -> list[str]:
    lowered = value.casefold()
    trait_map = (
        ("ответствен", "ответственность"),
        ("аккурат", "аккуратность"),
        ("вниматель", "внимательность"),
    )
    if sum(1 for marker, _ in trait_map if marker in lowered) < 2:
        return []

    return _dedupe_preserve_order(
        [normalized for marker, normalized in trait_map if marker in lowered]
    )


def classify_requirement_phrase(text: str) -> RequirementClassification:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" .;-–—•:").casefold()
    if any(
        marker in cleaned
        for marker in (
            "образование",
            "диплом",
            "высшее",
            "среднее профессиональное",
            "бакалавр",
            "магистр",
            "медицинск",
            "degree",
        )
    ):
        return "education"
    if any(
        marker in cleaned
        for marker in (
            "сертифик",
            "удостоверен",
            "аттестац",
            "лиценз",
            "допуск",
            "certification",
            "certificate",
        )
    ):
        return "certification"
    if any(
        marker in cleaned
        for marker in (
            "python",
            "fastapi",
            "postgres",
            "sql",
            "docker",
            "redis",
            "pytest",
            "api",
            "fmcg",
            "мерчандайз",
            "планограмм",
            "розничные продажи",
            "сантех",
            "инженерн",
            "трубопровод",
        )
    ):
        return "skill"
    return "competency"


def is_ignored_requirement_header(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•:").casefold()
    if cleaned in IGNORED_REQUIREMENT_HEADERS:
        return True

    return any(
        cleaned.startswith(f"{header}:") or cleaned.startswith(f"{header} ")
        for header in (
            "образование",
            "профессиональные",
            "профессиональные навыки",
            "требования к квалификации",
        )
    )


def requirement_match_key(value: str) -> str:
    normalized = normalize_requirement_phrase(value)
    key = re.sub(r"\s+", " ", normalized).strip(" .;-–—•").casefold()

    aliases = {
        "проектная документация": "ведение проектной документации",
        "ведение документации": "ведение проектной документации",
        "ведение проектной документации": "ведение проектной документации",
    }

    return aliases.get(key, key)
