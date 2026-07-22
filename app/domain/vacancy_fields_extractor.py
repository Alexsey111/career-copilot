# app\domain\vacancy_fields_extractor.py

"""Детерминированное извлечение структурированных полей вакансии из текста.

Применяется при ручном импорте (когда пользователь вставил текст вакансии или
загрузил файл, но не заполнил company/location/salary/...). Текст hh-вакансии
после копирования со страницы имеет узнаваемую шапку:

    Описание
    Специалист по внедрению искусственного интеллекта
    от 100 000 ₽ за месяц, до вычета налогов
    Выплаты: два раза в месяц
    Опыт работы: не требуется
    Полная занятость
    Оформление: ...
    График: 5/2
    Рабочие часы: 8
    Формат работы: удалённо или гибрид
    ...
    Вас пригласили
    ЗЕБРА

Извлечение чисто регулярное — без LLM, чтобы импорт работал без доступа к
модели (см. Этап 4/биллинг: детерминированный путь — базовый).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.vacancy_title_extractor import extract_vacancy_title


@dataclass
class VacancyFields:
    title: str | None = None
    company: str | None = None
    location: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None


_CURRENCY_MAP = {
    "₽": "RUB",
    "руб": "RUB",
    "р.": "RUB",
    "€": "EUR",
    "eur": "EUR",
    "$": "USD",
    "usd": "USD",
}

# «от 100 000 ₽», «до 200 000 ₽», «100 000 - 200 000 ₽», «от 1 000 €»
_SALARY_FROM_RE = re.compile(r"от\s+([\d\s ]+?)\s*(?:₽|руб|р\.|€|eur|\$|usd)", re.IGNORECASE)
_SALARY_TO_RE = re.compile(r"до\s+([\d\s ]+?)\s*(?:₽|руб|р\.|€|eur|\$|usd)", re.IGNORECASE)
_SALARY_RANGE_RE = re.compile(
    r"([\d\s ]+?)\s*[-–—]\s*([\d\s ]+?)\s*(?:₽|руб|р\.|€|eur|\$|usd)",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(r"(₽|руб|р\.|€|eur|\$|usd)", re.IGNORECASE)

# «Опыт работы: не требуется», «Опыт работы: 1-3 года», «Опыт: 3–6 лет»
_EXPERIENCE_RE = re.compile(r"опыт\s+работы?\s*[:：]\s*(.+)", re.IGNORECASE)

# «Полная занятость» / «Частичная занятость» / «Проектная работа» / «Стажировка»
_EMPLOYMENT_RE = re.compile(
    r"\b(полная\s+занятость|частичная\s+занятость|проектная\s+работа|стажировка|подработка)\b",
    re.IGNORECASE,
)

# «Формат работы: удалённо или гибрид», «Формат работы: удаленка»
_FORMAT_RE = re.compile(r"формат\s+работы\s*[:：]\s*(.+)", re.IGNORECASE)

# «Вас пригласили» (иногда с опечаткой латинской «c»), дальше идёт компания
_INVITED_RE = re.compile(r"^\s*ва[сsc]\s+пригласил", re.IGNORECASE)


def _clean_number(value: str) -> int | None:
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _detect_currency(text: str) -> str | None:
    match = _CURRENCY_RE.search(text)
    if not match:
        return None
    return _CURRENCY_MAP.get(match.group(1).strip().lower().rstrip("."), "RUB")


def _normalize_experience(raw: str) -> str:
    value = raw.strip().lower()
    if not value:
        return ""
    if "не треб" in value or "нет опыта" in value or "без опыта" in value or "не нужен" in value:
        return "Нет опыта"
    # Диапазоны проверяем раньше одиночного «6 лет», иначе «3-6 лет»
    # попадёт в ветку «Более 6 лет» (подстрока «6 лет»).
    if "3" in value and "6" in value:
        return "От 3 до 6 лет"
    if ("1" in value or "одного" in value) and ("3" in value or "трёх" in value or "трех" in value):
        return "От 1 года до 3 лет"
    if "более 6" in value or "больше 6" in value:
        return "Более 6 лет"
    # fallback — отдадим как есть, но обрежем по первому разделителю/концу строки
    return raw.strip().split(";", 1)[0].strip().capitalize()


def extract_vacancy_fields(text: str, *, fallback_title: str = "") -> VacancyFields:
    if not text or not text.strip():
        return VacancyFields(title=fallback_title or None)

    lines = [ln.strip() for ln in text.splitlines()]
    non_empty = [ln for ln in lines if ln]
    head_text = "\n".join(non_empty[:60])

    fields = VacancyFields()

    # title — переиспользуем существующий экстрактор (он уже skip'ает шапку hh).
    fields.title = extract_vacancy_title(text, fallback=fallback_title) or None

    # salary
    salary_from = _clean_number(_SALARY_FROM_RE.search(head_text).group(1)) if _SALARY_FROM_RE.search(head_text) else None
    salary_to = _clean_number(_SALARY_TO_RE.search(head_text).group(1)) if _SALARY_TO_RE.search(head_text) else None
    if salary_from is None and salary_to is None:
        rng = _SALARY_RANGE_RE.search(head_text)
        if rng:
            salary_from = _clean_number(rng.group(1))
            salary_to = _clean_number(rng.group(2))
    fields.salary_from = salary_from
    fields.salary_to = salary_to
    fields.salary_currency = _detect_currency(head_text)

    # experience
    exp_match = _EXPERIENCE_RE.search(head_text)
    if exp_match:
        normalized = _normalize_experience(exp_match.group(1))
        if normalized:
            fields.experience_level = normalized

    # employment
    emp_match = _EMPLOYMENT_RE.search(head_text)
    if emp_match:
        fields.employment_type = emp_match.group(1).strip().capitalize()

    # location / format
    fmt_match = _FORMAT_RE.search(head_text)
    if fmt_match:
        fields.location = fmt_match.group(1).strip().capitalize()

    # company — первая непустая строка после «Вас пригласили».
    for idx, line in enumerate(non_empty):
        if _INVITED_RE.match(line):
            for candidate in non_empty[idx + 1 : idx + 4]:
                if not candidate:
                    continue
                # рейтинг «4,9» / «4 отзыва» — не компания.
                if re.fullmatch(r"[\d,\.]+\s*(отзыв.*)?", candidate, re.IGNORECASE):
                    continue
                if _EMPLOYMENT_RE.search(candidate) or _EXPERIENCE_RE.search(candidate):
                    continue
                fields.company = candidate.strip()
                break
            break

    return fields