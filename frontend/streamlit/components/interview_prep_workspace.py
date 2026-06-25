# frontend\streamlit\components\interview_prep_workspace.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient


INTERVIEW_ANSWER_QUALITY_METRIC_LABELS = {
    "star_completeness": "STAR-структура",
    "evidence_usage": "Доказательства",
    "specificity": "Конкретика",
    "overclaim_safety": "Безопасность утверждений",
    "readiness": "Готовность ответа",
}


@dataclass(frozen=True, slots=True)
class InterviewPrepSessionDescriptor:
    session_id: str
    application_id: str
    vacancy_id: str
    prep_status: str
    readiness_score: int | None


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
        "keyword overlap": "Совпадает с требованиями вакансии",
        "skills overlap": "Навыки совпадают с требованиями вакансии",
        "snippet text overlap": "Описание проекта совпадает с требованиями вакансии",
        "related skill overlap": "Связанный навык поддерживает требование вакансии",
        "совпадает с доменным контекстом": "Связано с предметной областью вакансии",
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
    current_marker = " · текущий отклик" if current_application_id and application_id == current_application_id else ""
    return (
        f"{index}. {prep_status} · {readiness} · app …{app_suffix} · "
        f"{created_date} · {session_id[:8]}{current_marker}"
    )


def _sanitize_evidence_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    blocked_markers = [
        "extracted as a",
        "normalized contribution signal",
        "candidate ownership must be reviewed",
        "before strong use in documents",
        "implementation signal",
        "workflow automation signal",
    ]

    lowered = text.lower()
    cut_positions = [
        lowered.find(marker)
        for marker in blocked_markers
        if lowered.find(marker) >= 0
    ]

    if cut_positions:
        text = text[: min(cut_positions)].strip(" .;:-")

    return text


def _looks_like_uuid(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False

    try:
        UUID(text)
    except ValueError:
        return False

    return True


def _is_insufficient_grounding(answer: dict[str, Any] | None) -> bool:
    if not isinstance(answer, dict):
        return False
    return str(answer.get("grounding_status") or "").strip().lower() == "insufficient_evidence"


def _collect_evidence_by_competency(
    *,
    questions: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}

    for question in questions:
        competency_key = _normalize_key(question.get("competency_key"))
        if not competency_key:
            continue

        for item in question.get("recommended_evidence") or []:
            result.setdefault(competency_key, []).append(item)

    for item in evidence_links:
        competency_key = _normalize_key(item.get("competency_key"))
        if not competency_key:
            continue
        result.setdefault(competency_key, []).append(item)

    return result


def _best_fact_status(items: list[dict[str, Any]]) -> str | None:
    statuses = {
        str(item.get("fact_status") or "").strip().lower()
        for item in items
        if str(item.get("fact_status") or "").strip()
    }
    if "confirmed" in statuses:
        return "confirmed"
    if "user_provided" in statuses:
        return "user_provided"
    if "needs_confirmation" in statuses:
        return "needs_confirmation"
    if "partial" in statuses:
        return "partial"
    if statuses:
        return sorted(statuses)[0]
    return None


def _render_readiness_panel(readiness: dict[str, Any] | None) -> None:
    readiness = readiness or {}
    blockers = readiness.get("blockers") or []
    warnings = readiness.get("warnings") or []

    if readiness.get("ready"):
        st.success("Готово к подготовке к интервью ✅")
    else:
        st.warning("Нужно подтвердить факты для полной подготовки ⚠️")

    col_ready, col_blockers, col_warnings, col_score = st.columns(4)

    with col_ready:
        st.metric("Готово", "Да" if readiness.get("ready") else "Нет")
    with col_blockers:
        st.metric("Блокеры", len(blockers))
    with col_warnings:
        st.metric("Предупреждения", len(warnings))
    with col_score:
        st.metric("Оценка", _format_score(readiness.get("score")))

    question_summary = readiness.get("question_summary") or {}

    if question_summary:
        st.markdown("### Покрытие вопросов")

        by_category = question_summary.get("by_category") or {}

        col_q1, col_q2, col_q3, col_q4 = st.columns(4)

        with col_q1:
            st.metric(
                "Всего вопросов",
                question_summary.get("total", 0),
            )

        with col_q2:
            st.metric(
                "С доказательствами",
                question_summary.get("with_evidence_count", 0),
            )

        with col_q3:
            st.metric(
                "Сложных зон",
                question_summary.get("careful_answer_count", 0),
            )

        with col_q4:
            st.metric(
                "Категорий",
                len(by_category),
            )

        if by_category:
            st.markdown("**Распределение вопросов**")

            rows = [
                {
                    "Категория": _humanize_question_category(category),
                    "Количество": count,
                }
                for category, count in sorted(by_category.items())
            ]

            st.dataframe(
                rows,
                width="stretch",
                hide_index=True,
            )

    if blockers:
        st.markdown("**Блокеры**")
        for blocker in blockers:
            st.markdown(f"- {blocker}")
        st.caption(
            "Это не ошибка. Система нашла возможные доказательства, "
            "но они ещё не подтверждены пользователем. Подтвердите релевантный опыт "
            "или используйте вопросы как черновик подготовки."
        )

    if warnings:
        st.markdown("**Предупреждения**")
        for warning in warnings:
            st.markdown(f"- {warning}")

    roadmap = readiness.get("roadmap") or {}
    steps = roadmap.get("steps") or []

    if steps:
        st.markdown("### План повышения готовности")

        current_score = roadmap.get("current_score")
        projected_score = roadmap.get("projected_score")

        col_now, col_future = st.columns(2)

        with col_now:
            st.metric(
                "Текущая готовность",
                _format_score(current_score),
            )

        with col_future:
            st.metric(
                "После выполнения шагов",
                _format_score(projected_score),
            )

        for step in steps:
            with st.container(border=True):
                st.markdown(
                    f"**Шаг {step.get('order')}**"
                )

                st.write(step.get("title"))

                st.caption(
                    f"Ожидаемый прирост: +{step.get('expected_gain', 0)}"
                )


def _render_competency_coverage(
    *,
    competency_coverage_matrix: list[dict[str, Any]] | None,
    competency_map: dict[str, Any] | None,
    questions: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
    weak_areas: list[dict[str, Any]],
) -> None:
    st.markdown("### Покрытие компетенций доказательствами")
    st.caption(
        "Показывает, какие требования вакансии уже подтверждены, "
        "какие требуют подтверждения, а где доказательств пока нет."
    )

    matrix = [
        item
        for item in competency_coverage_matrix or []
        if isinstance(item, dict)
    ]
    if matrix:
        coverage_labels = {
            "covered": "Подтверждено",
            "needs_confirmation": "Нужно подтвердить",
            "missing": "Нет подтверждённых доказательств",
            "unknown": "Не определено",
        }
        rows = [
            {
                "Статус": _evidence_status_icon(
                    item.get("fact_status") or item.get("evidence_status")
                ),
                "Компетенция": (
                    item.get("competency_label")
                    or item.get("competency_key")
                    or "—"
                ),
                "Покрытие": coverage_labels.get(
                    _normalize_key(item.get("coverage_status")),
                    _humanize_display_text(item.get("coverage_status") or "Не определено"),
                ),
                "Найдено примеров": item.get("evidence_count", 0),
                "Комментарий": item.get("reason") or "—",
            }
            for item in matrix
        ]
    else:
        competency_map = competency_map or {}
        required_skills = competency_map.get("required_skills") or []

        if not required_skills:
            st.info("Обязательные компетенции не извлечены.")
            return

        evidence_by_competency = _collect_evidence_by_competency(
            questions=questions,
            evidence_links=evidence_links,
        )
        weak_by_competency = {
            _normalize_key(item.get("competency_key")): item
            for item in weak_areas
            if item.get("competency_key")
        }

        rows = []
        for skill in required_skills:
            key = _normalize_key(skill.get("key"))
            label = skill.get("label") or skill.get("key") or "—"
            evidence_items = evidence_by_competency.get(key, [])
            fact_status = _best_fact_status(evidence_items)

            if fact_status in {"confirmed", "user_provided"}:
                status_text = "Подтверждено"
            elif fact_status in {"needs_confirmation", "partial"}:
                status_text = "Нужно подтвердить"
            elif key in weak_by_competency:
                status_text = "Нет подтверждённых доказательств"
            else:
                status_text = "Не определено"

            rows.append(
                {
                    "Статус": _evidence_status_icon(
                        fact_status if evidence_items else None
                    ),
                    "Компетенция": label,
                    "Покрытие": status_text,
                    "Найдено примеров": len(evidence_items),
                    "Комментарий": (
                        weak_by_competency.get(key, {}).get("message")
                        if key in weak_by_competency
                        else "Есть подтверждающие примеры"
                        if evidence_items
                        else "Примеры не найдены"
                    ),
                }
            )

    st.dataframe(rows, width="stretch", hide_index=True)

    st.caption(
        "✅ подтверждено · ⚠️ найдено, но требует подтверждения · "
        "❌ подтверждающих примеров нет"
    )


def _render_competency_map(competency_map: dict[str, Any] | None) -> None:
    competency_map = competency_map or {}

    st.markdown("### Карта компетенций")
    col_skills, col_behavioral = st.columns(2)

    with col_skills:
        st.markdown("#### Обязательные навыки")
        required_skills = competency_map.get("required_skills") or []
        if required_skills:
            for item in required_skills:
                st.markdown(f"- {_humanize_display_text(item.get('label') or item.get('key'))}")
        else:
            st.caption("Обязательные навыки не извлечены.")

        domain_requirements = competency_map.get("domain_requirements") or []
        if domain_requirements:
            st.markdown("**Предметная область**")
            for item in domain_requirements:
                label = item.get("label") if isinstance(item, dict) else item
                if label:
                    st.markdown(f"- {_humanize_display_text(label)}")

    with col_behavioral:
        st.markdown("#### Поведенческие сигналы")
        behavioral_signals = competency_map.get("behavioral_signals") or []
        if behavioral_signals:
            for signal in behavioral_signals:
                st.markdown(f"- {_humanize_competency_value(signal)}")
        else:
            st.caption("Поведенческие сигналы не извлечены.")

    col_seniority, col_domain = st.columns(2)

    with col_seniority:
        st.markdown("#### Ожидания по уровню")
        seniority = competency_map.get("seniority_expectations") or {}
        if seniority:
            st.write(f"Уровень: {_humanize_seniority_level(seniority.get('level'))}")
            for signal in seniority.get("signals") or []:
                st.markdown(f"- {_humanize_competency_value(signal)}")
        else:
            st.caption("Ожидания по уровню не извлечены.")

    with col_domain:
        st.markdown("#### Фокус интервью")
        domain_focus_areas = (
            competency_map.get("domain_focus_areas")
            or competency_map.get("domain_expectations")
            or []
        )
        if domain_focus_areas:
            for item in domain_focus_areas:
                st.markdown(f"- {_humanize_display_text(item)}")
        else:
            st.caption("Фокус интервью не извлечён.")


def _render_suggested_answer(answer: dict[str, Any] | None) -> None:
    if not isinstance(answer, dict) or not answer:
        return

    insufficient_grounding = _is_insufficient_grounding(answer)

    _render_answer_quality(answer)

    with st.expander("Черновик ответа", expanded=False):
        if insufficient_grounding:
            st.caption("У нас пока нет доказательств. Вот что нужно собрать.")
        else:
            st.caption("Черновик ответа. Проверьте и адаптируйте под свой реальный опыт.")

        fields = [
            ("Ситуация", answer.get("situation")),
            ("Задача", answer.get("task")),
            ("Действия", answer.get("action")),
            ("Результат", answer.get("result")),
        ]
        for label, value in fields:
            value_text = str(value or "").strip()
            if value_text:
                st.markdown(f"**{label}:** {_humanize_display_text(value_text)}")

    tech_stack = [
        str(item).strip()
        for item in (answer.get("tech_stack") or [])
        if str(item).strip()
    ]
    if tech_stack:
        with st.expander("Технологии", expanded=False):
            st.markdown(", ".join(tech_stack))

    tradeoffs = [
        str(item).strip()
        for item in (answer.get("tradeoffs") or [])
        if str(item).strip()
    ]
    if tradeoffs:
        title = "Что нужно собрать" if insufficient_grounding else "Компромиссы и ограничения"
        with st.expander(title, expanded=False):
            for item in tradeoffs:
                st.markdown(f"- {_humanize_display_text(item)}")

    talking_points = [
        str(item).strip()
        for item in (answer.get("talking_points") or [])
        if str(item).strip()
    ]
    if talking_points:
        title = (
            "Что рассказать на интервью после подтверждения"
            if insufficient_grounding
            else "Что подчеркнуть на интервью"
        )
        with st.expander(title, expanded=False):
            for item in talking_points:
                st.markdown(f"- {_humanize_display_text(item)}")


def _render_answer_quality(answer: dict[str, Any]) -> None:
    quality = answer.get("quality") or {}
    if not isinstance(quality, dict) or not quality:
        return

    score = quality.get("score")
    grade = _humanize_answer_quality_grade(quality.get("grade"))
    metrics = quality.get("metrics") or {}
    strengths = quality.get("strengths") or []
    improvements = quality.get("improvements") or []

    with st.expander("Качество ответа", expanded=False):
        col_score, col_grade = st.columns(2)
        with col_score:
            st.metric("Оценка", _format_score(score))
        with col_grade:
            st.metric("Уровень", grade)

        if metrics:
            st.markdown("**Метрики**")
            for key, value in metrics.items():
                label = INTERVIEW_ANSWER_QUALITY_METRIC_LABELS.get(
                    str(key),
                    str(key).replace("_", " "),
                )
                st.metric(label, value)

        if strengths:
            st.markdown("**Сильные стороны**")
            for item in strengths:
                st.markdown(f"- {_humanize_display_text(item)}")

        if improvements:
            st.markdown("**Что улучшить**")
            for item in improvements:
                st.markdown(f"- {_humanize_display_text(item)}")


def _render_question_group(questions: list[dict[str, Any]]) -> None:
    if not questions:
        st.info("Сгенерированных вопросов пока нет.")
        return

    st.markdown("### Вопросы")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        grouped.setdefault(str(question.get("category") or "unknown"), []).append(question)

    for category, items in grouped.items():
        with st.expander(
            f"{_humanize_question_category(category)} ({len(items)})",
            expanded=category in {"technical", "gap-risk"},
        ):
            for question in items:
                with st.container(border=True):
                    st.markdown(f"**{_humanize_display_text(question.get('prompt') or 'Вопрос')}**")
                    if question.get("answer_format"):
                        st.caption(
                            f"Формат ответа: {_humanize_answer_format(question.get('answer_format'))}"
                        )
                    if question.get("competency_name") or question.get("competency_key"):
                        competency_name = _normalize_competency_label(
                            question.get("competency_name") or question.get("competency_key")
                        )
                        st.caption(
                            "Компетенция: "
                            f"{_humanize_display_text(competency_name)}"
                        )

                    suggested_answer = question.get("suggested_answer")
                    _render_suggested_answer(suggested_answer)

                    evidence = question.get("recommended_evidence") or []
                    rationale_title = (
                        "Почему системе пока не хватает доказательств"
                        if _is_insufficient_grounding(suggested_answer)
                        else "Почему система предлагает этот пример"
                    )
                    with st.expander(rationale_title, expanded=False):
                        if evidence:
                            for item in evidence:
                                st.markdown(f"- {item.get('title')}")
                                reason = item.get("reason")
                                if reason:
                                    st.caption(_humanize_reason(reason))
                        else:
                            if _is_insufficient_grounding(suggested_answer):
                                st.caption(
                                    "Нужно собрать подтверждённые факты, результат и конкретные действия."
                                )
                            else:
                                st.caption("Пока не привязано подтверждённое доказательство.")


def _render_question_supporting_evidence(
    client: CareerCopilotApiClient,
    *,
    question: dict[str, Any],
    selected_session: dict[str, Any],
    token: str | None,
) -> None:
    recommended = question.get("recommended_evidence") or []
    evidence_links = selected_session.get("evidence_links") or []
    question_id = str(question.get("question_id") or "").strip()

    if not recommended and evidence_links:
        recommended = [
            {
                "achievement_id": item.get("achievement_id"),
                "title": item.get("achievement_title"),
                "score": item.get("score"),
                "reason": item.get("reason"),
            }
            for item in evidence_links
            if str(item.get("question_id") or "").strip() == question_id
        ]

    st.markdown("##### Поддерживающие доказательства")
    if not recommended:
        st.caption("Для этого вопроса ещё не выбраны поддерживающие доказательства.")
        return

    for item in recommended:
        achievement_id = item.get("achievement_id")
        evidence_id = str(achievement_id or "").strip()
        title = str(item.get("title") or "Подтверждающий опыт").strip()
        reason = str(item.get("reason") or "").strip() or "—"
        score = _format_score(item.get("score"))

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"Почему это поможет в ответе: {_humanize_reason(reason)}")

            if not _looks_like_uuid(achievement_id):
                st.caption("Детали доказательства недоступны для этого источника.")
                continue

            if not evidence_id:
                st.caption("Детали этого доказательства пока недоступны.")
                continue

            try:
                snippet = client.get_evidence_snippet(evidence_id, token=token)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    st.caption("Детали доказательства недоступны, показана краткая версия.")
                    continue

                st.error(f"Не удалось загрузить детали доказательства: HTTP {exc.response.status_code}")
                continue
            except httpx.RequestError as exc:
                st.caption(f"Не удалось загрузить детали доказательства: {exc}")
                continue
            except ValueError as exc:
                st.caption(f"Не удалось загрузить детали доказательства: {exc}")
                continue

            if not isinstance(snippet, dict):
                st.caption("Сервер вернул неожиданные детали доказательства.")
                continue

            st.caption(
                "Источник: "
                f"{_humanize_evidence_source(snippet.get('source_type') or snippet.get('source'))}"
                " · "
                f"{_humanize_evidence_fact_status(snippet.get('fact_status'))}"
            )

            star_summary = snippet.get("star_summary") or snippet.get("star_summary_json") or {}
            if isinstance(star_summary, dict) and star_summary:
                star_parts = [
                    f"{_humanize_star_field(key)}={_sanitize_evidence_text(value)}"
                    for key, value in star_summary.items()
                    if key in {"situation", "task", "action", "result"}
                    if _sanitize_evidence_text(value) not in ("", "—")
                ]
                if star_parts:
                    st.caption("STAR-превью: " + ", ".join(star_parts))

            snippet_text = _sanitize_evidence_text(snippet.get("snippet_text"))
            if snippet_text:
                st.write(snippet_text)


def _render_evidence_links(evidence_links: list[dict[str, Any]]) -> None:
    st.markdown("### Связки STAR-доказательств")
    if not evidence_links:
        st.caption("Связок доказательств пока нет.")
        return

    rows = []
    for item in evidence_links:
        rows.append(
            {
                "Вопрос": _humanize_question_category(item.get("question_category")),
                "Компетенция": _humanize_competency_value(item.get("competency_key")),
                "Достижение": _humanize_display_text(item.get("achievement_title") or "—"),
                "Почему подходит": _humanize_reason(item.get("reason")),
            }
        )

    st.dataframe(rows, width="stretch", hide_index=True)


def _render_weak_areas(weak_areas: list[dict[str, Any]]) -> None:
    st.markdown("### Слабые зоны")
    if not weak_areas:
        st.success("Детерминированные слабые зоны не обнаружены.")
        return

    for item in weak_areas:
        severity = str(item.get("severity") or "").lower()
        text = _humanize_weak_area_message(item.get("message"))
        if severity == "blocker":
            st.error(text)
        elif severity == "warning":
            st.warning(text)
        else:
            st.info(text)
        if item.get("category") or item.get("competency_key"):
            st.caption(
                f"{_humanize_question_category(item.get('category'))} · "
                f"{_humanize_competency_value(item.get('competency_key'))}"
            )


def _render_session_cleanup_action(
    client: CareerCopilotApiClient,
    *,
    token: str | None,
    selection_state_key: str,
    sessions: list[dict[str, Any]],
    current_application_id: str | None,
) -> None:
    st.markdown("### Управление сессиями")
    st.caption(
        "Выберите одну или несколько сессий подготовки к интервью, которые больше не нужны."
    )

    if not sessions:
        st.info("Сессии подготовки к интервью пока не созданы.")
        return

    session_ids: list[str] = []
    labels: dict[str, str] = {}
    default_selected: list[str] = []
    for index, item in enumerate(sessions, start=1):
        session_id = str(item.get("id") or "").strip()
        if not session_id:
            continue
        session_ids.append(session_id)
        labels[session_id] = _format_session_cleanup_label(
            item,
            index=index,
            current_application_id=current_application_id,
        )
        if current_application_id and str(item.get("application_id") or "").strip() == current_application_id:
            default_selected.append(session_id)

    if not session_ids:
        st.info("У доступных сессий нет валидных id.")
        return

    selected_session_ids = st.multiselect(
        "Сессии для удаления",
        options=session_ids,
        default=default_selected,
        format_func=lambda value: labels.get(value, value),
        key=f"{selection_state_key}_delete_picker",
    )

    if not selected_session_ids:
        st.caption("Отметьте одну или несколько сессий, чтобы активировать удаление.")
        return

    st.warning("Удаление нельзя отменить. Будут удалены только отмеченные сессии.")

    if not st.button(
        "Удалить выбранные сессии",
        type="primary",
        width="stretch",
        key=f"{selection_state_key}_delete_selected_interview_prep_sessions",
    ):
        return

    try:
        result = client.delete_interview_prep_sessions_by_ids(
            session_ids=selected_session_ids,
            token=token,
        )
        st.code(result)
    except httpx.HTTPStatusError as exc:
        st.error(f"Сервер вернул HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к серверу")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Сервер вернул неожиданный ответ")
        st.code(str(exc))
        return

    deleted_count = int(result.get("deleted_count") or 0) if isinstance(result, dict) else 0
    st.session_state.pop(selection_state_key, None)
    st.session_state.pop(f"{selection_state_key}_delete_picker", None)
    st.success(f"Удалено сессий: {deleted_count}")
    st.rerun()


def _render_create_action(
    client: CareerCopilotApiClient,
    *,
    token: str | None,
    selection_state_key: str,
) -> None:
    application = st.session_state.get("application")
    if not application:
        st.info(
            "В сессии Streamlit нет текущего отклика. "
            "Сначала создайте отклик со статусом «отклик отправлен»."
        )
        return

    if str(application.get("status") or "").lower() != "applied":
        st.info("Подготовка к интервью доступна после перевода отклика в статус «отклик отправлен».")
        return

    application_id = str(application.get("id") or "").strip()
    if not application_id:
        st.warning("У текущего отклика нет id.")
        return

    st.caption("Сессия будет связана с текущим откликом.")
    with st.expander("Технические детали", expanded=False):
        st.caption(f"application_id: {application_id}")
        st.caption(f"vacancy_id: {application.get('vacancy_id')}")

    button_key = f"{selection_state_key}_create_interview_prep_session"

    if st.button(
        "Создать сессию подготовки к интервью",
        type="primary",
        width="stretch",
        key=button_key,
    ):
        try:
            session = client.create_interview_prep_session(
                application_id=application_id,
                token=token,
            )
        except httpx.HTTPStatusError as exc:
            st.error(f"Сервер вернул HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к серверу")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Сервер вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(session, dict):
            st.error("Сервер вернул неожиданный формат сессии")
            st.json(session)
            return

        st.session_state[selection_state_key] = str(session.get("id") or "")
        st.success("Сессия подготовки к интервью создана")
        st.rerun()


def render_interview_prep_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
    selection_state_key: str = "interview_prep_workspace_selection",
) -> None:
    st.header("Подготовка к интервью")
    st.caption(
        "Детерминированный слой подготовки: карта компетенций, генерация вопросов, "
        "связки с доказательствами, слабые зоны и готовность."
    )

    if not token:
        st.warning("Войдите, чтобы открыть подготовку к интервью.")
        return

    _render_create_action(
        client,
        token=token,
        selection_state_key=selection_state_key,
    )

    try:
        sessions = client.list_interview_prep_sessions(token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Сервер вернул HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к серверу")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Сервер вернул неожиданный ответ")
        st.code(str(exc))
        return

    if not isinstance(sessions, list):
        st.error("Сервер вернул неожиданный список сессий")
        st.json(sessions)
        return

    current_application = st.session_state.get("application") or {}
    current_application_id = str(current_application.get("id") or "").strip()

    _render_session_cleanup_action(
        client,
        token=token,
        selection_state_key=selection_state_key,
        sessions=sessions,
        current_application_id=current_application_id,
    )

    if current_application_id:
        sessions = [
            item for item in sessions
            if str(item.get("application_id") or "").strip() == current_application_id
        ]

    if not sessions:
        st.info("Сессии подготовки к интервью пока не созданы.")
        return

    normalized_sessions: list[InterviewPrepSessionDescriptor] = []
    for item in sessions:
        session_id = str(item.get("id") or "").strip()
        if not session_id:
            continue
        normalized_sessions.append(
            InterviewPrepSessionDescriptor(
                session_id=session_id,
                application_id=str(item.get("application_id") or ""),
                vacancy_id=str(item.get("vacancy_id") or ""),
                prep_status=str(item.get("prep_status") or "draft"),
                readiness_score=item.get("readiness_score"),
            )
        )

    if not normalized_sessions:
        st.warning("Не найдено доступных сессий подготовки.")
        return

    total_count = len(normalized_sessions)
    ready_count = sum(1 for item in normalized_sessions if item.prep_status == "ready")
    draft_count = sum(1 for item in normalized_sessions if item.prep_status == "draft")
    readiness_values = [
        int(item.readiness_score)
        for item in normalized_sessions
        if item.readiness_score is not None
    ]
    average_readiness = (
        round(sum(readiness_values) / len(readiness_values))
        if readiness_values
        else None
    )

    col_total, col_ready, col_draft, col_avg = st.columns(4)
    with col_total:
        st.metric("Всего", total_count)
    with col_ready:
        st.metric("Готово", ready_count)
    with col_draft:
        st.metric("Черновиков", draft_count)
    with col_avg:
        st.metric(
            "Средняя оценка",
            f"{average_readiness} / 100" if average_readiness is not None else "—",
        )

    session_display_names = {
        item.session_id: f"Сессия подготовки {idx}"
        for idx, item in enumerate(normalized_sessions, start=1)
    }

    rows = [
        {
            "Сессия": session_display_names[item.session_id],
            "Отклик": "текущий" if item.application_id else "—",
            "Статус": _humanize_prep_status(item.prep_status),
            "Готовность": _format_score(item.readiness_score),
        }
        for item in normalized_sessions
    ]
    st.dataframe(rows, width="stretch", hide_index=True)

    options = [item.session_id for item in normalized_sessions]
    labels = {
        item.session_id: (
            f"{session_display_names[item.session_id]} · "
            f"{_humanize_prep_status(item.prep_status)} · "
            f"{_format_score(item.readiness_score)}"
        )
        for item in normalized_sessions
    }
    selected_session_id = st.session_state.get(selection_state_key)
    if selected_session_id not in options:
        selected_session_id = options[0]

    selected_session_id = st.selectbox(
        "Выберите сессию",
        options=options,
        index=options.index(selected_session_id),
        format_func=lambda value: labels.get(value, value),
        key=f"{selection_state_key}_picker",
    )
    st.session_state[selection_state_key] = selected_session_id

    try:
        selected_session = client.get_interview_prep_session(selected_session_id, token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Сервер вернул HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к серверу")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Сервер вернул неожиданный ответ")
        st.code(str(exc))
        return

    if not isinstance(selected_session, dict):
        st.error("Сервер вернул неожиданный формат сессии")
        st.json(selected_session)
        return

    st.markdown("### Сессия подготовки")
    st.caption(f"Статус: {_humanize_prep_status(selected_session.get('prep_status'))}")
    st.caption(f"Готовность: {_format_score(selected_session.get('readiness_score'))}")
    st.caption("Связана с текущим откликом")

    with st.expander("Технические детали", expanded=False):
        st.caption(f"id: {selected_session.get('id')}")
        st.caption(f"application_id: {selected_session.get('application_id')}")
        st.caption(f"vacancy_id: {selected_session.get('vacancy_id')}")
        st.caption(f"prep_status: {selected_session.get('prep_status')}")
        st.caption(f"readiness_score: {selected_session.get('readiness_score')}")

    readiness = selected_session.get("readiness") or {}
    _render_readiness_panel(readiness)
    st.divider()
    _render_competency_coverage(
        competency_coverage_matrix=readiness.get("competency_coverage_matrix"),
        competency_map=selected_session.get("competency_map"),
        questions=selected_session.get("questions") or [],
        evidence_links=selected_session.get("evidence_links") or [],
        weak_areas=selected_session.get("weak_areas") or [],
    )
    st.divider()
    _render_competency_map(selected_session.get("competency_map"))
    st.divider()
    _render_question_group(selected_session.get("questions") or [])
    st.divider()
    st.markdown("### Происхождение доказательств по вопросам")
    questions = selected_session.get("questions") or []
    if not questions:
        st.caption("Вопросов пока нет.")
    else:
        for question in questions:
            with st.container(border=True):
                st.markdown(f"**{_humanize_display_text(question.get('prompt') or 'Вопрос')}**")
                if question.get("answer_format"):
                    st.caption(
                        f"Формат ответа: {_humanize_answer_format(question.get('answer_format'))}"
                    )
                if question.get("competency_name") or question.get("competency_key"):
                    competency_name = _normalize_competency_label(
                        question.get("competency_name") or question.get("competency_key")
                    )
                    st.caption(
                        "Компетенция: "
                        f"{_humanize_display_text(competency_name)}"
                    )
                _render_question_supporting_evidence(
                    client,
                    question=question,
                    selected_session=selected_session,
                    token=token,
                )
    st.divider()
    _render_evidence_links(selected_session.get("evidence_links") or [])
    st.divider()
    _render_weak_areas(selected_session.get("weak_areas") or [])

    # Raw JSON intentionally hidden to keep the operator view compact.
