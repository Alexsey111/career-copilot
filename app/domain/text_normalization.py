from __future__ import annotations

import re


# Эмодзи-пиктограммы и variation-селекторы. Убираются на границе загрузки
# текста (импорт вакансии, парсер резюме, GitHub-intake), чтобы
# детерминированный downstream-анализ никогда не видел эмодзи-префиксы
# вида «✅ Что нужно будет делать» / «⭐️ Будет преимуществом» и не
# нуждался в поп_RULE-обработке. Регекс покрывает основные emoji-блоки:
#   - U+1F000–U+1FAFF  emoticons / transport / misc pictographs / supplemental
#   - U+1F1E6–U+1F1FF  regional indicator symbols (флаги-литеры)
#   - U+2600–U+27BF    misc symbols & pictographs (✅ ✈ ✨ ✔ ❤ ➡ ☕ ⚡)
#   - U+2B00–U+2BFF    misc symbols & arrows (⭐ ⭕)
#   - U+FE0F/U+FE0E    variation selectors (emoji-presentation)
#   - U+200D           zero-width joiner (составные эмодзи)
# © ® ™ намеренно НЕ вырезаются — встречаются в названиях компаний как текст.
EMOJI_PATTERN = re.compile(
    "["
    "🀀-🫿"   # emoticons / transport / misc pictographs / supplemental
    "🇦-🇿"   # regional indicator symbols (флаги-литеры)
    "☀-➿"            # misc symbols & pictographs: ✅ ✈ ✨ ✔ ❤ ➡ ☕ ⚡
    "⬀-⯿"            # misc symbols & arrows: ⭐ ⭕
    "️︎"             # variation selectors (emoji-presentation)
    "‍"                   # zero-width joiner (составные эмодзи)
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text: str | None) -> str:
    """Удалить эмодзи-пиктограммы и variation-селекторы из текста.

    Применяется один раз на границе загрузки, чтобы ни один downstream-модуль
    не получал эмодзи и не дублировал их обработку. Лишние пробелы, остающиеся
    после вырезания, схлопываются вызывающей стороной в ``_normalize_text``.
    """
    if not text:
        return ""
    return EMOJI_PATTERN.sub("", text)


def strip_emoji_deep(value):
    """Рекурсивно вырезать эмодзи из всех строк в dict/list/str-структуре.

    Для sanitizing content_json генерируемых документов (резюме/письмо):
    LLM-NLG может вставить эмодзи в поле (target_position, summary), хотя
    юзер явно просил «эмодзи нигде не использовать». Граница загрузки
    (strip_emoji) покрывает импорт; здесь покрываем LLM-вывод. Нестроковые
    значения (числа, bool, None) проходят как есть.
    """
    if isinstance(value, str):
        return strip_emoji(value)
    if isinstance(value, dict):
        return {key: strip_emoji_deep(val) for key, val in value.items()}
    if isinstance(value, list):
        return [strip_emoji_deep(item) for item in value]
    return value


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
