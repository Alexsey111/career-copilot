# app\domain\case_prep.py

"""Доменные модели подготовки к кейсам / work sample (Этап 9.E).

Детерминированный, explainable набор practice-кейсов по вакансии. **Без AI**:
кейсы — шаблонные сценарии по типу роли/гэпам, без выдуманных компаний/чисел/имён
(coaching artifact, не factual claim). ``requires_human_review`` всегда True —
кандидат адаптирует шаблон к реальному промпту работодателя.

См. ``docs/interview_prep_contract.md`` (Stable Case Types) и образец домена
``app/domain/career_strategy.py``. Переиспользует ``has_leadership_tokens`` и
``build_competency_key`` из ``app/domain/interview_prep.py``.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.domain.interview_prep import build_competency_key, has_leadership_tokens


# Заглушки названий компаний — никогда не должны появляться в title/prompt
# (кейсы — шаблоны без выдуманных specifics). Короткие маркеры (inc/ltd/ооо)
# проверяются по границам слов, чтобы не совпасть с подстрокой ("incident").
_COMPANY_NAME_MARKERS = ("acme", "globex", "contoso", "testco")
_COMPANY_SUFFIX_RE = re.compile(r"\b(inc|ltd|ооо|зао|пао)\b", re.IGNORECASE)


STABLE_CASE_TYPES: tuple[str, ...] = (
    "system_design",
    "debugging_scenario",
    "data_analysis",
    "behavioral_case",
    "take_home_brief",
)

# Порядок приоритета выбора типов кейсов (раньше = важнее).
_CASE_TYPE_PRIORITY: tuple[str, ...] = (
    "system_design",
    "debugging_scenario",
    "data_analysis",
    "behavioral_case",
    "take_home_brief",
)

# Токены, сигнализирующие о системном дизайне / архитектуре.
_SYSTEM_DESIGN_TOKENS = (
    "system design",
    "архитектур",
    "scalab",
    "highload",
    "high load",
    "distributed system",
    "распределённ",
    "распределенн",
)

# Токены, сигнализирующие о debugging / расследовании инцидентов.
_DEBUGGING_TOKENS = (
    "debug",
    "troubleshoot",
    "incident",
    "root cause",
    "on-call",
    "oncall",
    "on call",
    "лог",
    "инцидент",
    "расследован",
    "диагност",
    "fault",
    "outage",
)

# Токены data analysis / аналитики.
_DATA_TOKENS = (
    "data analysis",
    "analytics",
    "sql",
    "etl",
    "pipeline",
    "dashboard",
    "data modeling",
    "data modelling",
    "tableau",
    "статист",
    "метрик",
    "аналитик",
)

# Seniority-маркеры — добавляют system_design к behavioral_case.
_SENIORITY_TOKENS = ("senior", "lead", "staff", "principal", "manager", "руководит")

# Маркеры выдуманных specifics — НЕ должны появляться в title/prompt (guard).
_FABRICATED_MARKERS = (
    "acme",
    "globex",
    "contoso",
    "testco",
)

# fact_status, допускаемые в recommended_evidence для practice-кейсов
# (строже, чем usable_matches в VacancyFitService — без needs_confirmation,
# т.к. practice-кейс опирается на подтверждённый STAR).
_RECOMMENDED_FACT_STATUSES = ("confirmed", "user_provided")

_TITLE_MAP: dict[str, str] = {
    "system_design": "Практика системного дизайна",
    "debugging_scenario": "Практика отладки и инцидентов",
    "data_analysis": "Практика анализа данных",
    "behavioral_case": "Поведенческий кейс (STAR)",
    "take_home_brief": "Тестовое задание (take-home)",
}


def _has_token(text: str, tokens: tuple[str, ...]) -> bool:
    normalized = (text or "").casefold()
    return any(token in normalized for token in tokens)


def _requirement_text(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(
        item.get("requirement")
        or item.get("text")
        or item.get("keyword")
        or ""
    ).strip()


def _severity_of(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(item.get("severity") or "").strip().lower()


@dataclass(slots=True)
class CaseProvenance:
    """Provenance набора кейсов: источники, human review (всегда True)."""

    sources: list[str] = field(default_factory=list)
    requires_human_review: bool = True
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "requires_human_review": self.requires_human_review,
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class PracticeCase:
    """Один practice-кейс: шаблонный сценарий + rubric + структура ответа."""

    case_id: str
    case_type: str
    title: str
    prompt: str
    framework: str
    time_guidance: str
    rubric: list[str] = field(default_factory=list)
    suggested_approach: list[str] = field(default_factory=list)
    recommended_evidence: list[dict[str, Any]] = field(default_factory=list)
    competency_key: str | None = None
    source_requirement: str | None = None
    gap_severity: str | None = None
    provenance: CaseProvenance = field(default_factory=CaseProvenance)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "title": self.title,
            "prompt": self.prompt,
            "framework": self.framework,
            "time_guidance": self.time_guidance,
            "rubric": list(self.rubric),
            "suggested_approach": list(self.suggested_approach),
            "recommended_evidence": [dict(e) for e in self.recommended_evidence],
            "competency_key": self.competency_key,
            "source_requirement": self.source_requirement,
            "gap_severity": self.gap_severity,
            "provenance": self.provenance.as_dict(),
        }


@dataclass(slots=True)
class CasePrepReport:
    """On-demand отчёт practice-кейсов по вакансии (без персистентности)."""

    vacancy_id: Any
    cases: list[PracticeCase] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    provenance: CaseProvenance = field(default_factory=CaseProvenance)

    def as_dict(self) -> dict[str, Any]:
        return {
            "vacancy_id": str(self.vacancy_id),
            "cases": [c.as_dict() for c in self.cases],
            "meta": dict(self.meta),
            "provenance": self.provenance.as_dict(),
        }


def select_case_types(
    requirements: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    *,
    max_cases: int = 5,
) -> list[str]:
    """Детерминированный выбор типов practice-кейсов по требованиям и гэпам.

    Правила (по тексту requirement/gap):
    - leadership-токены → ``behavioral_case``; + seniority-маркеры →
      ``system_design`` (старшие роли традиционно получают system-design кейс).
    - ``_SYSTEM_DESIGN_TOKENS`` → ``system_design``.
    - ``_DEBUGGING_TOKENS`` → ``debugging_scenario``.
    - ``_DATA_TOKENS`` → ``data_analysis``.
    - ≥1 critical (severity=="critical" в requirements/gaps) → ``take_home_brief``.
    Пусто → ``["behavioral_case"]``. Дедуп + порядок приоритета + обрезка ``max_cases``.
    """
    req_texts = [_requirement_text(r) for r in (requirements or [])]
    gap_texts = [_requirement_text(g) for g in (gaps or [])]
    all_texts = req_texts + gap_texts

    has_leadership = any(has_leadership_tokens(t.casefold()) for t in all_texts if t)
    has_seniority = any(_has_token(t, _SENIORITY_TOKENS) for t in req_texts if t)
    has_system_design = any(_has_token(t, _SYSTEM_DESIGN_TOKENS) for t in all_texts if t)
    has_debugging = any(_has_token(t, _DEBUGGING_TOKENS) for t in all_texts if t)
    has_data = any(_has_token(t, _DATA_TOKENS) for t in all_texts if t)
    has_critical = any(
        _severity_of(item) == "critical"
        for item in list(requirements or []) + list(gaps or [])
    )

    selected: list[str] = []
    if has_system_design or (has_leadership and has_seniority):
        selected.append("system_design")
    if has_debugging:
        selected.append("debugging_scenario")
    if has_data:
        selected.append("data_analysis")
    if has_leadership:
        selected.append("behavioral_case")
    if has_critical:
        selected.append("take_home_brief")

    if not selected:
        selected.append("behavioral_case")

    # Дедуп + стабильный порядок приоритета.
    ordered = [ct for ct in _CASE_TYPE_PRIORITY if ct in dict.fromkeys(selected)]
    return ordered[: max(1, max_cases)]


def build_rubric(case_type: str) -> list[str]:
    """Статические критерии самопроверки для типа кейса (≥4 пункта)."""
    rubrics: dict[str, list[str]] = {
        "system_design": [
            "Масштабируемость учтена и по возможности оценена количественно",
            "Выделены режимы отказов и деградация с запасом прочности",
            "Компромиссы прописаны явно, с рассмотренными альтернативами",
            "Понятны поток данных и зоны ответственности компонентов",
            "Допущения сформулированы и ограничены по области",
        ],
        "debugging_scenario": [
            "Гипотеза формулируется до действий",
            "Логи и факты подтверждают или опровергают гипотезу",
            "Переменные изолируются по одной за раз",
            "Откат/страховка продумываются до изменения состояния",
            "Устраняется корневая причина, а не симптом",
        ],
        "data_analysis": [
            "Вопрос сформулирован до любых запросов",
            "Определения метрик явные и согласованные",
            "Сегментация обоснована и осмысленна",
            "Учтены конфаундеры и оговорки по качеству данных",
            "Вывод ведёт к действию, а не просто описывает",
        ],
        "behavioral_case": [
            "Ситуация конкретная и определённая",
            "Задача и ваша роль описаны ясно",
            "Действие — что сделали ИМЕННО ВЫ, со specifics",
            "Результат по возможности оцифрован",
            "Видна ответственность и извлечённый урок",
        ],
        "take_home_brief": [
            "Объём уточнён до начала работы",
            "Допущения зафиксированы",
            "Сначала реализован базовый happy path",
            "Тесты и краевые случаи проработаны",
            "Описаны компромиссы и следующие шаги",
        ],
    }
    return list(rubrics.get(case_type, rubrics["behavioral_case"]))


def build_suggested_approach(case_type: str) -> list[str]:
    """Статические шаги подхода для типа кейса."""
    approaches: dict[str, list[str]] = {
        "system_design": [
            "Перефразируйте задачу и уточните объём и ограничения",
            "Набросайте компоненты верхнего уровня и поток данных",
            "Проработайте ёмкость, узкие места и режимы отказов",
            "Назовите явные компромиссы и отвергнутые альтернативы",
            "Сформулируйте, что стали бы делать первым и почему",
        ],
        "debugging_scenario": [
            "Перефразируйте симптом и опишите, как выглядит «здоровое» состояние",
            "Составьте приоритизированный список гипотез",
            "Выберите самую дешёвую проверку для верхней гипотезы",
            "Изолируйте по одной переменной и фиксируйте наблюдения",
            "Предложите исправление и откат, затем убедитесь, что причина устранена",
        ],
        "data_analysis": [
            "Сформулируйте бизнес-вопрос одним предложением",
            "Определите метрики и нужную гранулярность",
            "Продумайте сегменты и сравнения, отвечающие на вопрос",
            "Заранее отметьте оговорки по качеству данных и конфаундеры",
            "Сформулируйте вывод и следующее действие, которое из него следует",
        ],
        "behavioral_case": [
            "Выберите конкретную ситуацию под компетенцию",
            "Опишите задачу и вашу зону ответственности",
            "Расскажите действие по шагам со specifics",
            "Оцифруйте результат и назовите, чему научились",
            "Свяжите историю с ролью, на которую собеседуетесь",
        ],
        "take_home_brief": [
            "Уточните объём и критерии успеха до написания кода",
            "Зафиксируйте допущения",
            "Сначала сделайте базовый happy path и держите его рабочим",
            "Добавьте тесты и обработайте ключевые краевые случаи",
            "Опишите компромиссы, ограничения и что стали бы делать дальше",
        ],
    }
    return list(approaches.get(case_type, approaches["behavioral_case"]))


def _framework_for(case_type: str) -> str:
    # Методологические названия: акронимы (STAR, RTL) — универсальны, оставляем.
    # Описательные — переводим. Используется в UI «Фреймворк: …».
    return {
        "system_design": "гипотезы-ориентированный",
        "debugging_scenario": "гипотезы-ориентированный",
        "data_analysis": "структурированный разбор",
        "behavioral_case": "STAR",
        "take_home_brief": "RTL",
    }.get(case_type, "STAR")


def _time_guidance_for(case_type: str) -> str:
    # Band, не конкретный дедлайн (non-goal: выдуманные сроки/даты).
    return {
        "system_design": "60–90 минут",
        "debugging_scenario": "60–90 минут",
        "data_analysis": "60–90 минут",
        "behavioral_case": "15–30 минут",
        "take_home_brief": "2–4 часа, тестовое на дом",
    }.get(case_type, "30–60 минут")


def _build_prompt(case_type: str, requirement_text: str, gap_keyword: str) -> str:
    """Rule-based шаблон промпта, параметризуется ТОЛЬКО requirement/gap keyword.

    БЕЗ выдуманных компаний/чисел/имён (non-goal). Пустой requirement →
    ``gap_keyword`` или обобщённая «ключевая область роли».
    """
    subject = (requirement_text or gap_keyword or "ключевая область роли").strip()
    templates: dict[str, str] = {
        "system_design": (
            f"Спроектируйте систему для области, подразумеваемой «{subject}». "
            "Опишите компоненты, поток данных, компромиссы и режимы отказов. "
            "Сформулируйте допущения; не предполагайте конкретный продукт или компанию."
        ),
        "debugging_scenario": (
            f"Сервис с поведением, связанным с «{subject}», деградировал. "
            "Опишите, как стали бы исследовать и изолировать причину. "
            "Сформулируйте гипотезы и проверки, которые применили бы."
        ),
        "data_analysis": (
            f"Дан запрос, затрагивающий «{subject}». Определите анализ: "
            "вопрос, метрики, сегментацию и вывод, "
            "к которому стали бы стремиться."
        ),
        "behavioral_case": (
            f"Опишите ситуацию из вашего опыта, где вы работали с "
            f"«{subject}». Используйте STAR и оцифруйте результат."
        ),
        "take_home_brief": (
            f"Короткое тестовое на дом по «{subject}». Уточните объём, реализуйте "
            "базовый путь, покройте краевые случаи и опишите компромиссы и следующие шаги."
        ),
    }
    return templates.get(case_type, templates["behavioral_case"])


def _case_id(case_type: str, competency_key: str, source_requirement: str, prompt: str) -> str:
    digest = hashlib.sha1(
        "|".join([case_type, competency_key, source_requirement, prompt]).encode("utf-8")
    ).hexdigest()
    return f"ipc_{digest[:16]}"


def build_case(
    case_type: str,
    *,
    requirement: dict[str, Any] | None = None,
    gap: dict[str, Any] | None = None,
    recommended_evidence: list[dict[str, Any]] | None = None,
) -> PracticeCase:
    """Собрать один practice-кейс из якоря (requirement/gap) и подобранной evidence."""
    req_text = _requirement_text(requirement)
    gap_text = _requirement_text(gap)
    source_requirement = req_text or gap_text or None
    gap_severity = _severity_of(gap) or _severity_of(requirement) or None
    gap_keyword = gap_text or (requirement.get("keyword") if requirement else "") or ""

    prompt = _build_prompt(case_type, req_text, str(gap_keyword or ""))
    competency_key = build_competency_key(source_requirement or case_type)
    case_id = _case_id(case_type, competency_key, source_requirement or "", prompt)
    title = _TITLE_MAP[case_type] + (f" — {source_requirement}" if source_requirement else "")

    provenance = CaseProvenance(
        sources=["vacancy_fit"],
        requires_human_review=True,
        notes=[
            "детерминированный сценарий-шаблон — адаптируйте под реальный промпт работодателя",
            "без выдуманных подробностей (компании, числа, имена)",
        ],
    )

    return PracticeCase(
        case_id=case_id,
        case_type=case_type,
        title=title,
        prompt=prompt,
        framework=_framework_for(case_type),
        time_guidance=_time_guidance_for(case_type),
        rubric=build_rubric(case_type),
        suggested_approach=build_suggested_approach(case_type),
        recommended_evidence=list(recommended_evidence or []),
        competency_key=competency_key,
        source_requirement=source_requirement,
        gap_severity=gap_severity,
        provenance=provenance,
    )


def build_meta(
    case_types: list[str],
    requirements: list[dict[str, Any]],
    *,
    max_cases: int = 5,
) -> dict[str, Any]:
    """Мета-описание набора: counts, наличие critical gap, лимит."""
    has_critical = any(_severity_of(r) == "critical" for r in requirements or [])
    counts = Counter(case_types)
    return {
        "total": len(case_types),
        "case_type_counts": dict(counts),
        "has_critical_gap": has_critical,
        "max_cases": max_cases,
    }


def assert_no_fabricated_specifics(cases: list[PracticeCase]) -> bool:
    """Guard: в title/prompt нет выдуманных компаний/чисел/имён. Для тестов.

    Названия-заглушки (acme/globex/...) — любое вхождение; суффиксы
    (inc/ltd/ооо) — только по границе слова (иначе "incident" ложно совпадёт).
    """
    for case in cases:
        text = f"{case.title} {case.prompt}".casefold()
        if any(marker in text for marker in _FABRICATED_MARKERS):
            return False
        if _COMPANY_SUFFIX_RE.search(text):
            return False
    return True