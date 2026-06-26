from __future__ import annotations

import re
from typing import Any


def _format_score(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{round(float(value))} / 100"
    except (TypeError, ValueError):
        return str(value)


def _humanize_prep_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    labels = {
        "draft": "черновик",
        "ready": "готова",
        "blocked": "нужны подтверждения",
        "in_progress": "в работе",
    }
    return labels.get(status, status or "—")


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _evidence_status_icon(fact_status: str | None) -> str:
    status = str(fact_status or "").strip().lower()
    if status in {"confirmed", "user_provided"}:
        return "✅"
    if status in {"needs_confirmation", "partial"}:
        return "⚠️"
    if status == "rejected":
        return "🛑"
    return "❌"


def _fact_status_badge(fact_status: str | None) -> str:
    status = str(fact_status or "").strip().lower()
    labels = {
        "confirmed": "✓ Подтверждено пользователем",
        "user_provided": "✓ Есть в резюме/профиле",
        "needs_confirmation": "⚠ Требует подтверждения",
        "partial": "⚠ Подтверждено частично",
        "rejected": "✗ Отклонено",
        "unverified": "⚠ Требует проверки",
    }
    return labels.get(status, "⚠ Требует проверки")


def _humanize_reason(reason: Any) -> str:
    text = str(reason or "").strip()
    if not text or text == "—":
        return "Этот пример связан с компетенцией из вакансии."

    lowered = text.lower()
    replacements = {
        "keyword overlap": "Совпадает с требованием вакансии",
        "skills overlap": "Навык совпадает с требованием вакансии",
        "snippet text overlap": "Описание опыта связано с требованием вакансии",
        "related skill overlap": "Связанный навык поддерживает требование вакансии",
        "слабое текстовое совпадение": "Есть связь с темой вопроса",
        "есть слабое текстовое совпадение": "Есть связь с темой вопроса",
        "совпадает с доменным контекстом": "Связано с предметной областью вакансии",
        "связано с предметной областью вакансии": "Связано с предметной областью вакансии",
        "факт подтверждён": "Факт подтверждён",
        "есть измеримый результат": "Есть измеримый результат",
        "recommended": "Рекомендовано для ответа на этот вопрос",
    }
    for key, label in replacements.items():
        if key in lowered:
            return label
    return text


def _humanize_strength(value: Any) -> str:
    strength = str(value or "").strip().lower()
    return {
        "strong": "сильное подтверждение",
        "medium": "частичное подтверждение",
        "weak": "слабое подтверждение",
    }.get(strength, "требует проверки")


def _humanize_evidence_source(value: Any) -> str:
    source = str(value or "").strip().lower()
    if source in {"resume_structured", "structured_resume_extraction_v2"}:
        return "Импортировано из резюме"
    if source in {"manual", "achievement"}:
        return "Добавлено кандидатом"
    if source in {"github_public", "github_repository_analysis"}:
        return "Импортировано из GitHub"
    return "Источник не указан"


def _humanize_evidence_fact_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"confirmed", "user_provided"}:
        return "Подтверждено кандидатом"
    if status in {"needs_confirmation", "partial", "unverified"}:
        return "Требует подтверждения"
    if status == "rejected":
        return "Отклонено"
    return "Статус не указан"


def _humanize_question_category(value: Any) -> str:
    category = str(value or "").strip().lower()
    labels = {
        "technical": "технический вопрос",
        "behavioral": "поведенческий вопрос",
        "gap-risk": "вопрос по слабой зоне",
        "evidence_probe": "уточнение по опыту",
        "project_deep_dive": "разбор проекта",
        "leadership": "лидерский опыт",
        "unknown": "без категории",
    }
    return labels.get(category, category or "без категории")


def _humanize_answer_format(value: Any) -> str:
    answer_format = str(value or "").strip()
    labels = {
        "STAR": "STAR",
        "STAR_or_example": "STAR или пример из опыта",
        "STAR_or_project_context": "STAR или контекст проекта",
        "honest_gap_response": "честный ответ о слабой зоне",
    }
    return labels.get(answer_format, answer_format or "не указан")


def _humanize_answer_quality_grade(value: Any) -> str:
    grade = str(value or "").strip().lower()
    labels = {
        "excellent": "отличный",
        "good": "хороший",
        "needs_work": "требует доработки",
        "weak": "слабый",
    }
    return labels.get(grade, grade or "—")


def _humanize_star_field(value: Any) -> str:
    key = str(value or "").strip().lower()
    labels = {
        "situation": "Ситуация",
        "task": "Задача",
        "action": "Действия",
        "result": "Результат",
    }
    return labels.get(key, str(value or ""))


def _humanize_competency_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"

    normalized = text.lower().replace(" ", "_")
    labels = {
        "ownership": "ответственность",
        "communication": "коммуникация",
        "leadership": "лидерство",
        "collaboration": "сотрудничество",
        "cross_functional_collaboration": "кросс-функциональное сотрудничество",
        "mentoring": "наставничество",
        "learning_agility": "обучаемость",
        "stakeholder_management": "работа со стейкхолдерами",
        "architecture_tradeoffs": "архитектурные компромиссы",
        "independent_delivery": "самостоятельное доведение задач до результата",
        "tradeoff_reasoning": "обоснование компромиссов",
        "fundamentals": "базовые принципы",
        "adobe_photoshop": "Adobe Photoshop",
        "coreldraw": "CorelDRAW",
    }
    if normalized in labels:
        return labels[normalized]

    return text.replace("_", " ")


def _normalize_competency_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    replacements = {
        "коммуникацию": "коммуникация",
        "коммуникацией": "коммуникация",
        "ответственность": "ответственность",
        "сотрудничество": "сотрудничество",
    }

    normalized = replacements.get(text.lower(), text)
    if text[:1].isupper() and normalized:
        return normalized[:1].upper() + normalized[1:]
    return normalized


def _humanize_seniority_level(value: Any) -> str:
    level = str(value or "").strip().lower()
    labels = {
        "junior": "junior",
        "middle": "middle",
        "senior": "senior",
        "lead": "lead",
        "staff": "staff",
        "principal": "principal",
    }
    return labels.get(level, str(value or "—"))


def _humanize_display_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    replacements = {
        "проявили ownership": "проявили ответственность",
        "проявили communication": "проявили коммуникацию",
        "проявили collaboration": "проявили сотрудничество",
        "проявили learning agility": "проявили обучаемость",
        "компетенцией: коммуникацию": "компетенцией: коммуникация",
        "теме коммуникацию": "теме коммуникация",
        "grounded in confirmed evidence": "привязанным к подтверждённым фактам",
        "confirmed evidence": "подтверждённые факты",
        "claims": "утверждений",
        "claim": "утверждение",
        "evidence": "доказательства",
        "ownership": "ответственность",
        "communication": "коммуникация",
        "collaboration": "сотрудничество",
        "independent delivery": "самостоятельное доведение задач до результата",
        "tradeoff reasoning": "обоснование компромиссов",
        "learning agility": "обучаемость",
        "architecture tradeoffs": "архитектурные компромиссы",
        "cross-functional collaboration": "кросс-функциональное сотрудничество",
    }
    for source, target in replacements.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
    text = text.replace("компетенцией: коммуникацию", "компетенцией: коммуникация")
    text = text.replace("теме коммуникацию", "теме коммуникация")
    return text


def _humanize_weak_area_message(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Слабая зона"

    match = re.fullmatch(r"No confirmed (.+) evidence\.?", text, flags=re.IGNORECASE)
    if match:
        competency = _humanize_competency_value(match.group(1))
        return f"Нет подтверждённых доказательств по компетенции: {competency}"

    return text


def _format_session_cleanup_label(
    item: dict[str, Any],
    *,
    index: int,
    current_application_id: str | None,
) -> str:
    session_id = str(item.get("id") or "").strip()
    application_id = str(item.get("application_id") or "").strip()
    prep_status = _humanize_prep_status(item.get("prep_status"))
    readiness = _format_score(item.get("readiness_score"))
    created_at = str(item.get("created_at") or "").strip()
    created_date = created_at[:10] if created_at else "—"
    app_suffix = application_id[-8:] if application_id else "—"
    current_marker = (
        " · текущий отклик"
        if current_application_id and application_id == current_application_id
        else ""
    )
    return (
        f"{index}. {prep_status} · {readiness} · app …{app_suffix} · "
        f"{created_date} · {session_id[:8]}{current_marker}"
    )
