# frontend\streamlit\app.py

from __future__ import annotations

import os
import importlib.util
import sys
from html import escape
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

app_module = sys.modules.get("app")
if app_module is not None and not hasattr(app_module, "__path__"):
    del sys.modules["app"]

from api_client import CareerCopilotApiClient, DEFAULT_API_BASE_URL
from components import (
    render_career_strategy_workspace_tab,
    render_document_review_workspace_tab,
    render_evidence_workspace_tab,
    render_interview_prep_workspace_tab,
)

_DEMO_SCENARIOS_PATH = PROJECT_ROOT / "app" / "core" / "demo_scenarios.py"
_demo_spec = importlib.util.spec_from_file_location(
    "career_copilot_demo_scenarios",
    _DEMO_SCENARIOS_PATH,
)
if _demo_spec is None or _demo_spec.loader is None:
    raise RuntimeError(f"Unable to load demo scenarios from {_DEMO_SCENARIOS_PATH}")
_demo_module = importlib.util.module_from_spec(_demo_spec)
_demo_spec.loader.exec_module(_demo_module)
get_demo_scenarios = _demo_module.get_demo_scenarios


st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧭",
    layout="wide",
)


APPLICATION_STATUS_LABELS = {
    "draft": "Черновик",
    "ready": "Готов к отправке",
    "applied": "Отправлен вручную",
    "screening": "Скрининг",
    "interview": "Интервью",
    "rejected": "Отказ",
    "offer": "Оффер",
    "withdrawn": "Отозван",
}

APPLICATION_OUTCOME_LABELS = {
    "rejected": "Отказ",
    "offer": "Оффер",
}

APPLICATION_REMINDER_LABELS = {
    "draft_stale": "Черновик без активности",
    "ready_not_submitted": "Готов к отправке, но не отправлен",
    "follow_up_missing": "Нет follow-up по отклику",
}

DEMO_VACANCY_TITLE_LABELS = {
    "Backend Developer": "Backend-разработчик",
}

DEMO_COMPANY_LABELS = {
    "Test Company": "Тестовая компания",
}

DEMO_LOCATION_LABELS = {
    "Remote": "Удалённо",
}

RISK_LEVEL_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

CONFIDENCE_LEVEL_LABELS = {
    "high": "Высокая уверенность",
    "medium": "Средняя уверенность",
    "low": "Низкая уверенность",
    "needs_review": "Требует проверки",
}

ACTION_SEVERITY_LABELS = {
    "blocker": "Блокер",
    "warning": "Предупреждение",
    "info": "Инфо",
}

ENTITY_TYPE_LABELS = {
    "document": "Документ",
    "interview_prep": "Подготовка к интервью",
}

DOCUMENT_KIND_LABELS = {
    "resume": "Резюме",
    "cover_letter": "Сопроводительное письмо",
}

SEVERITY_TONES = {
    "blocker": {"bg": "#FEE2E2", "fg": "#991B1B"},
    "warning": {"bg": "#FFEDD5", "fg": "#9A3412"},
    "info": {"bg": "#DBEAFE", "fg": "#1D4ED8"},
    "success": {"bg": "#DCFCE7", "fg": "#166534"},
    "neutral": {"bg": "#E5E7EB", "fg": "#374151"},
}

CONFIDENCE_TONES = {
    "high": "success",
    "medium": "warning",
    "low": "warning",
    "needs_review": "blocker",
}

RISK_LEVEL_TONES = {
    "low": "success",
    "medium": "warning",
    "high": "blocker",
}

ACTION_GROUP_ORDER = (
    "Resolve blockers",
    "Review unsupported claims",
    "Prepare interview gaps",
    "Improve confidence",
)

TRUST_PANEL_TEXT_REPLACEMENTS = {
    "Unified review summary from a single backend contract. No internal document or interview JSON is shown here.": (
        "Единая сводка проверки на одном backend-контракте. "
        "Внутренний JSON документов или интервью здесь не показывается."
    ),
    "No generated documents are available yet.": "Пока нет доступных сгенерированных документов.",
    "No active scoped documents available.": "Пока нет активных привязанных документов.",
    "No active document.": "Активный документ отсутствует.",
    "Current active scoped application": "Текущее активное приложение",
    "Active scoped documents": "Активные привязанные документы",
    "Demo scenarios": "Демо-сценарии",
    "Reset and verify commands": "Команды сброса и проверки",
    "Select document": "Выберите документ",
    "Select interview prep session": "Выберите сессию подготовки к интервью",
    "No interview prep sessions are available yet.": "Пока нет доступных сессий подготовки к интервью.",
    "No valid interview prep sessions are available.": "Нет валидных сессий подготовки к интервью.",
    "Entity id is missing.": "Не указан идентификатор сущности.",
    "Backend returned an unexpected response": "Backend вернул неожиданный ответ",
    "Backend returned an unexpected review summary payload": "Backend вернул неожиданный payload сводки проверки",
    "Unable to connect to backend": "Не удалось подключиться к backend",
    "No blockers detected. All critical claims confirmed. Interview prep readiness acceptable.": (
        "Блокеров не обнаружено. Все критичные утверждения подтверждены. "
        "Подготовка к интервью приемлема."
    ),
    "No blockers detected.": "Блокеров не обнаружено.",
    "No warnings detected.": "Предупреждений не обнаружено.",
    "All critical claims confirmed.": "Все критичные утверждения подтверждены.",
    "Interview prep readiness acceptable.": "Подготовка к интервью приемлема.",
    "No selected evidence was returned by the backend.": "Backend не вернул выбранные доказательства.",
    "No recommended actions. The review looks stable.": "Рекомендованных действий нет. Проверка выглядит стабильной.",
    "No confirmed Python evidence": "Нет подтверждённых доказательств по Python",
    "No confirmed Kubernetes evidence": "Нет подтверждённых доказательств по Kubernetes",
    "How would you honestly answer about the weak area: No confirmed Python evidence": (
        "Как вы честно ответите на вопрос о слабой зоне: Нет подтверждённых доказательств по Python"
    ),
    "How would you honestly answer about the weak area: No confirmed Kubernetes evidence": (
        "Как вы честно ответите на вопрос о слабой зоне: Нет подтверждённых доказательств по Kubernetes"
    ),
    "Resolve blockers": "Устранить блокеры",
    "Review unsupported claims": "Проверить неподтверждённые утверждения",
    "Prepare interview gaps": "Подготовить ответы на пробелы",
    "Improve confidence": "Повысить уверенность",
    "Resolve blocker": "Устранить блокер",
    "Interview Prep": "Подготовка к интервью",
    "Interview Question": "Вопрос интервью",
    "Prepare a careful gap-risk response": "Подготовьте аккуратный ответ на вопрос о пробеле",
    "Strong evidence": "Сильные доказательства",
    "Medium evidence": "Средние доказательства",
    "No confirmed evidence": "Нет подтверждённых доказательств",
    "Show evidence provenance": "Показать provenance доказательств",
    "Document": "Документ",
    "Interview prep": "Подготовка к интервью",
    "draft": "черновик",
    "Target id": "целевой ID",
    "Resume": "Резюме",
    "Cover Letter": "Сопроводительное письмо",
    "Claims requiring confirmation": "Утверждения, требующие подтверждения",
    "Gap-risk items": "Пункты с риском по пробелам",
    "Selected evidence": "Выбранные доказательства",
    "Recommended actions": "Рекомендованные действия",
    "Blockers": "Блокеры",
    "Warnings": "Предупреждения",
    "Risk": "Риск",
    "Ready": "Готово",
    "Human review": "Человеческая проверка",
    "Confidence": "Уверенность",
    "Required": "Требуется",
    "Not required": "Не требуется",
    "Ready": "Готово",
    "Blocked": "Есть блокировка",
    "No items.": "Элементов нет.",
    "Source": "Источник",
    "Generation mode": "Режим генерации",
    "Confidence level": "Уровень уверенности",
    "Requires human review": "Требуется ручная проверка",
    "Analysis id": "ID анализа",
    "Application id": "ID заявки",
    "Vacancy id": "ID вакансии",
    "Document id": "ID документа",
    "Question generation mode": "Режим генерации вопросов",
    "Selected achievement ids": "Выбранные ID достижений",
    "Selected evidence ids": "Выбранные ID доказательств",
    "Competency sources": "Источники компетенций",
    "Question source counts": "Количество источников вопросов",
    "target id": "целевой ID",
    "Backend": "Backend",
    "Ready": "Готово",
    "No active scoped application found yet.": "Активное приложение пока не найдено.",
    "No active scoped documents available.": "Активные привязанные документы пока не найдены.",
}


def format_application_status(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_STATUS_LABELS.get(value, value)


def format_optional_datetime(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ")[:19]


def format_application_outcome(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_OUTCOME_LABELS.get(value, value)


def format_vacancy_title(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_VACANCY_TITLE_LABELS.get(value, value)


def format_vacancy_company(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_COMPANY_LABELS.get(value, value)


def format_vacancy_location(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_LOCATION_LABELS.get(value, value)


def _format_label(value: str | None, labels: dict[str, str]) -> str:
    if not value:
        return "—"
    normalized = str(value).strip().lower()
    return labels.get(normalized, value)


def _translate_trust_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return TRUST_PANEL_TEXT_REPLACEMENTS.get(text, text)


def _format_confidence_value(provenance_summary: dict[str, Any] | None) -> str:
    provenance_summary = provenance_summary or {}
    confidence_level = str(provenance_summary.get("confidence_level") or "").strip().lower()
    confidence = provenance_summary.get("confidence")

    if confidence_level and confidence is not None:
        level_label = CONFIDENCE_LEVEL_LABELS.get(confidence_level, confidence_level)
        try:
            return f"{level_label} ({round(float(confidence), 2)})"
        except (TypeError, ValueError):
            return f"{level_label} ({confidence})"

    if confidence_level:
        return CONFIDENCE_LEVEL_LABELS.get(confidence_level, confidence_level)

    if confidence is not None:
        try:
            return f"{round(float(confidence), 2)}"
        except (TypeError, ValueError):
            return str(confidence)

    return "—"


def _render_badge(label: str, *, tone: str = "neutral") -> None:
    colors = SEVERITY_TONES.get(tone, SEVERITY_TONES["neutral"])
    st.markdown(
        (
            "<span style='display:inline-block;"
            "padding:0.25rem 0.65rem;"
            "border-radius:999px;"
            f"background:{colors['bg']};"
            f"color:{colors['fg']};"
            "font-size:0.78rem;"
            "font-weight:700;"
            "line-height:1.2;"
            "margin-right:0.35rem;"
            "margin-bottom:0.35rem;'>"
            f"{escape(label)}"
            "</span>"
        ),
        unsafe_allow_html=True,
    )


def _render_inline_badges(badges: list[tuple[str, str]]) -> None:
    if not badges:
        return
    columns = st.columns(len(badges))
    for column, (label, tone) in zip(columns, badges, strict=False):
        with column:
            _render_badge(label, tone=tone)


def _confidence_badge_tone(confidence_level: str | None) -> str:
    if not confidence_level:
        return "neutral"
    return CONFIDENCE_TONES.get(str(confidence_level).strip().lower(), "neutral")


def _risk_badge_tone(risk_level: str | None) -> str:
    if not risk_level:
        return "neutral"
    return RISK_LEVEL_TONES.get(str(risk_level).strip().lower(), "neutral")


def _action_badge_tone(severity: str | None) -> str:
    if not severity:
        return "neutral"
    normalized = str(severity).strip().lower()
    return normalized if normalized in SEVERITY_TONES else "neutral"


def _render_trust_panel_list(title: str, items: list[str]) -> None:
    st.markdown(f"**{_translate_trust_text(title)}**")
    if not items:
        st.caption(_translate_trust_text("No items."))
        return
    for item in items:
        st.markdown(f"- {_translate_trust_text(item)}")


def _humanize_document_kind_for_trust_panel(document_kind: str | None) -> str:
    if not document_kind:
        return "Документ"
    normalized = str(document_kind).strip().lower()
    return DOCUMENT_KIND_LABELS.get(normalized, document_kind)


def _normalize_action_group(action: dict[str, Any]) -> str:
    code = str(action.get("code") or "").strip().lower()
    target_type = str(action.get("target_type") or "").strip().lower()
    severity = str(action.get("severity") or "").strip().lower()
    label = str(action.get("label") or "").strip().lower()

    if code == "confirm_claim" or target_type == "document_claim":
        return "Review unsupported claims"

    if code in {"resolve_blocker"} or severity == "blocker":
        return "Resolve blockers"

    if code in {"prepare_gap_response"} or target_type == "interview_question" or "gap" in code or "gap" in label:
        return "Prepare interview gaps"

    if code in {"review_low_confidence", "attach_missing_evidence"} or severity in {"blocker", "warning"}:
        return "Improve confidence"

    return "Improve confidence"


def _group_review_actions(actions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {group: [] for group in ACTION_GROUP_ORDER}
    sorted_actions = sorted(
        [item for item in actions if isinstance(item, dict)],
        key=lambda item: (
            str(item.get("code") or ""),
            str(item.get("target_type") or ""),
            str(item.get("target_id") or ""),
            str(item.get("label") or ""),
        ),
    )
    for action in sorted_actions:
        grouped[_normalize_action_group(action)].append(action)
    return grouped


def _render_action_card(action: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(
            f"**{_translate_trust_text(str(action.get('label') or action.get('code') or 'Action'))}**"
        )
        badge_parts = [
            (
                _translate_trust_text(
                    ACTION_SEVERITY_LABELS.get(
                        str(action.get("severity") or "").strip().lower(),
                        str(action.get("severity") or "neutral").title(),
                    )
                ),
                _action_badge_tone(action.get("severity")),
            ),
        ]
        target_type = str(action.get("target_type") or "").strip()
        if target_type:
            badge_parts.append((_translate_trust_text(target_type.replace("_", " ").title()), "neutral"))
        _render_inline_badges(badge_parts)

        reason = str(action.get("reason") or "").strip()
        if reason:
            st.write(_translate_trust_text(reason))

        target_id = str(action.get("target_id") or "").strip()
        if target_id:
            st.caption(f"{_translate_trust_text('Target id')}: {target_id}")


def _render_grouped_actions(actions: list[dict[str, Any]]) -> None:
    grouped_actions = _group_review_actions(actions)
    rendered_any = False

    for group_name in ACTION_GROUP_ORDER:
        group_actions = grouped_actions.get(group_name) or []
        if not group_actions:
            continue
        rendered_any = True
        translated_group_name = _translate_trust_text(group_name)
        with st.expander(
            f"{translated_group_name} ({len(group_actions)})",
            expanded=group_name != "Improve confidence",
        ):
            for action in group_actions:
                _render_action_card(action)

    if not rendered_any:
        st.success(_translate_trust_text("No recommended actions. The review looks stable."))


def _render_provenance_summary(summary: dict[str, Any]) -> None:
    if not summary:
        st.success("Backend не вернул данные provenance.")
        return

    provenance_rows = [
        ("Source", summary.get("source")),
        ("Generation mode", summary.get("generation_mode")),
        ("Confidence level", summary.get("confidence_level")),
        ("Confidence", summary.get("confidence")),
        ("Requires human review", summary.get("requires_human_review")),
        ("Analysis id", summary.get("analysis_id")),
        ("Application id", summary.get("application_id")),
        ("Vacancy id", summary.get("vacancy_id")),
        ("Document id", summary.get("document_id")),
        ("Question generation mode", summary.get("question_generation_mode")),
    ]

    cols = st.columns(2)
    with cols[0]:
        for label, value in provenance_rows[: len(provenance_rows) // 2]:
            if value in (None, "", []):
                continue
            st.markdown(f"**{_translate_trust_text(label)}:** {value}")
    with cols[1]:
        for label, value in provenance_rows[len(provenance_rows) // 2 :]:
            if value in (None, "", []):
                continue
            st.markdown(f"**{_translate_trust_text(label)}:** {value}")

    selected_achievement_ids = summary.get("selected_achievement_ids") or []
    selected_evidence_ids = summary.get("selected_evidence_ids") or []
    competency_sources = summary.get("competency_sources") or []
    question_source_counts = summary.get("question_source_counts") or {}

    if selected_achievement_ids:
        st.caption(
            f"{_translate_trust_text('Selected achievement ids')}: "
            + ", ".join(str(item) for item in selected_achievement_ids)
        )
    if selected_evidence_ids:
        st.caption(
            f"{_translate_trust_text('Selected evidence ids')}: "
            + ", ".join(str(item) for item in selected_evidence_ids)
        )
    if competency_sources:
        st.caption(
            f"{_translate_trust_text('Competency sources')}: "
            + ", ".join(
                str(item.get("competency_key") or item.get("label") or "—")
                for item in competency_sources
                if isinstance(item, dict)
            )
        )
    if question_source_counts:
        st.caption(
            f"{_translate_trust_text('Question source counts')}: "
            + ", ".join(f"{key}={value}" for key, value in question_source_counts.items())
        )


def _render_system_health(client: CareerCopilotApiClient, *, token: str | None) -> None:
    st.header("Состояние системы")
    st.caption(
        "Оперативный снимок для пилотных демо: backend, база данных, "
        "seeded-данные, счётчики и текущее активное приложение в контексте."
    )

    backend_check = client.check_backend()
    _render_inline_badges(
        [
            ("Backend доступен" if backend_check.ok else "Backend недоступен", "success" if backend_check.ok else "blocker"),
            ("Токен входа есть" if token else "Требуется вход", "success" if token else "warning"),
        ]
    )

    if not token:
        st.info("Войдите, чтобы посмотреть текущее seeded-состояние и данные по scoped-приложению.")
        return

    try:
        diagnostics = client.get_system_health_diagnostics(token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend returned HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend returned an unexpected response")
        st.code(str(exc))
        return

    if not isinstance(diagnostics, dict):
        st.error("Backend returned an unexpected system health payload")
        st.json(diagnostics)
        return

    counts = diagnostics.get("counts") or {}
    demo_state = diagnostics.get("demo_state") or {}
    current_application = diagnostics.get("current_active_application") or {}
    active_documents = diagnostics.get("active_documents") or {}
    scenario_identifiers = diagnostics.get("scenario_identifiers") or get_demo_scenarios()

    col_backend, col_db, col_seeded, col_user = st.columns(4)
    with col_backend:
        st.metric(
            "Бэкенд",
            "Доступен" if diagnostics.get("backend_reachable") else "Недоступен",
        )
    with col_db:
        st.metric(
            "База данных",
            "Доступна" if diagnostics.get("db_reachable") else "Недоступна",
        )
    with col_seeded:
        st.metric(
            "Состояние демо",
            "Готово" if demo_state.get("has_demo_data") else "Пусто",
        )
    with col_user:
        current_user_id = str(diagnostics.get("current_user_id") or "").strip()
        st.metric("Текущий пользователь", current_user_id[:8] if current_user_id else "—")

    col_vacancies, col_applications, col_documents, col_sessions = st.columns(4)
    with col_vacancies:
        st.metric("Вакансии", counts.get("vacancies", 0))
    with col_applications:
        st.metric("Отклики", counts.get("applications", 0))
    with col_documents:
        st.metric("Документы", counts.get("documents", 0))
    with col_sessions:
        st.metric("Сессии интервью", counts.get("interview_sessions", 0))

    with st.container(border=True):
        st.markdown("### Текущее активное приложение в контексте")
        if current_application:
            st.json(
                {
                    "application_id": current_application.get("id"),
                    "vacancy_id": current_application.get("vacancy_id"),
                    "status": current_application.get("status"),
                    "source": current_application.get("source"),
                    "resume_document_id": current_application.get("resume_document_id"),
                    "cover_letter_document_id": current_application.get("cover_letter_document_id"),
                    "created_at": current_application.get("created_at"),
                    "updated_at": current_application.get("updated_at"),
                }
            )
        else:
            st.info("Активное приложение в контексте пока не найдено.")

    with st.container(border=True):
        st.markdown("### Активные документы в контексте")
        resume_document = active_documents.get("resume")
        cover_letter_document = active_documents.get("cover_letter")
        if not resume_document and not cover_letter_document:
            st.caption("Активные документы в контексте пока недоступны.")
        else:
            for label, document in (
                ("Резюме", resume_document),
                ("Сопроводительное письмо", cover_letter_document),
            ):
                with st.expander(label, expanded=False):
                    if not document:
                        st.caption("Активный документ отсутствует.")
                        continue
                    st.json(
                        {
                            "document_id": document.get("id"),
                            "vacancy_id": document.get("vacancy_id"),
                            "document_kind": document.get("document_kind"),
                            "version_label": document.get("version_label"),
                            "review_status": document.get("review_status"),
                            "is_active": document.get("is_active"),
                            "created_at": document.get("created_at"),
                            "updated_at": document.get("updated_at"),
                        }
                    )

    with st.expander("Демо-сценарии", expanded=True):
        for scenario in scenario_identifiers:
            if not isinstance(scenario, dict):
                continue
            label = str(scenario.get("label") or scenario.get("code") or "Scenario")
            code = str(scenario.get("code") or "").strip()
            description = str(scenario.get("description") or "").strip()
            with st.container(border=True):
                st.markdown(f"**{label}**")
                if code:
                    st.caption(code)
                if description:
                    st.write(description)

    with st.expander("Команды сброса и проверки", expanded=False):
        st.code(
            "python scripts/reset_demo_environment.py\n"
            "python scripts/check_demo_trust_states.py",
            language="bash",
        )


def _render_trust_panel(
    client: CareerCopilotApiClient,
    *,
    token: str | None,
) -> None:
    st.header("Панель доверия")
    st.caption(
        "Единая сводка проверки по одному backend-контракту. "
        "Внутренний JSON документов или интервью здесь не показывается."
    )

    if not token:
        st.info("Войдите, чтобы посмотреть панели доверия и review-summary.")
        return

    diagnostics: dict[str, Any] = {}
    active_documents: dict[str, Any] = {}
    current_application: dict[str, Any] = {}
    try:
        diagnostics = client.get_system_health_diagnostics(token=token)
    except Exception:
        diagnostics = {}
    if isinstance(diagnostics, dict):
        active_documents = diagnostics.get("active_documents") or {}
        current_application = diagnostics.get("current_active_application") or {}

    entity_type = st.radio(
        "Тип сущности",
        options=["document", "interview_prep"],
        horizontal=True,
        format_func=lambda value: ENTITY_TYPE_LABELS.get(value, value),
        key="trust_panel_entity_type",
    )

    entity_id = ""
    entity_label = "Сущность"

    if entity_type == "document":
        candidates: list[dict[str, Any]] = []
        seen_document_ids: set[str] = set()

        def _add_document_candidate(source_document: dict[str, Any] | None) -> None:
            if not isinstance(source_document, dict):
                return
            document_id = str(source_document.get("document_id") or source_document.get("id") or "").strip()
            if not document_id or document_id in seen_document_ids:
                return
            seen_document_ids.add(document_id)
            candidates.append(
                {
                    "id": document_id,
                    "label": (
                        f"{_humanize_document_kind_for_trust_panel(source_document.get('document_kind'))} "
                        f"· {document_id[:8]}"
                    ),
                }
            )

        for source_document in (
            st.session_state.get("generated_resume"),
            st.session_state.get("generated_cover_letter"),
        ):
            _add_document_candidate(source_document)

        for source_document in (
            active_documents.get("resume"),
            active_documents.get("cover_letter"),
        ):
            _add_document_candidate(source_document)

        if not candidates:
            application_context = st.session_state.get("application") or current_application
            vacancy_id = None
            if isinstance(application_context, dict):
                vacancy_id = str(application_context.get("vacancy_id") or "").strip() or None

            for document_kind, fallback_title in (
                ("resume", "Tailored Resume"),
                ("cover_letter", "Cover Letter"),
            ):
                try:
                    active_document = client.get_active_document(
                        document_kind=document_kind,
                        vacancy_id=vacancy_id,
                        token=token,
                    )
                except Exception:
                    continue

                document_id = str(active_document.get("id") or "").strip()
                if not document_id:
                    continue

                _add_document_candidate(
                    {
                        "document_id": document_id,
                        "document_kind": document_kind,
                    }
                )

        if not candidates:
            st.info(_translate_trust_text("No generated documents are available yet."))
            return

        options = [item["id"] for item in candidates]
        labels = {item["id"]: item["label"] for item in candidates}
        selected_document_id = st.session_state.get("trust_panel_document_id")
        if selected_document_id not in options:
            selected_document_id = options[0]
        selected_option = st.selectbox(
            "Выберите документ",
            options=options,
            index=options.index(selected_document_id),
            format_func=lambda value: labels.get(value, value),
            key="trust_panel_document_id",
        )
        entity_id = str(selected_option).strip()
        entity_label = labels.get(entity_id, "Документ")

    else:
        try:
            sessions = client.list_interview_prep_sessions(token=token)
        except Exception as exc:
            st.error(f"Не удалось загрузить сессии подготовки к интервью: {exc}")
            return

        if not isinstance(sessions, list) or not sessions:
            st.info(_translate_trust_text("No interview prep sessions are available yet."))
            return

        candidates = []
        for item in sessions:
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("id") or "").strip()
            if not session_id:
                continue
            status_label = _translate_trust_text(str(item.get("prep_status") or "draft"))
            candidates.append(
                {
                    "id": session_id,
                    "label": (
                        f"{status_label} · "
                        f"{session_id[:8]} · заявка {str(item.get('application_id') or '')[:8]}"
                    ),
                }
            )

        if not candidates:
            st.info(_translate_trust_text("No valid interview prep sessions are available."))
            return

        options = [item["id"] for item in candidates]
        labels = {item["id"]: item["label"] for item in candidates}
        selected_session_id = st.session_state.get("trust_panel_interview_prep_id")
        if selected_session_id not in options:
            selected_session_id = options[0]
        selected_option = st.selectbox(
            "Выберите сессию подготовки к интервью",
            options=options,
            index=options.index(selected_session_id),
            format_func=lambda value: labels.get(value, value),
            key="trust_panel_interview_prep_id",
        )
        entity_id = str(selected_option).strip()
        entity_label = labels.get(entity_id, "Сессия подготовки к интервью")

    if not entity_id:
        st.warning(_translate_trust_text("Entity id is missing."))
        return

    try:
        if entity_type == "document":
            summary = client.get_document_review_summary(entity_id, token=token)
        else:
            summary = client.get_review_summary(
                entity_type=entity_type,
                entity_id=entity_id,
                token=token,
            )
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend returned HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend returned an unexpected response")
        st.code(str(exc))
        return

    if not isinstance(summary, dict):
        st.error("Backend returned an unexpected review summary payload")
        st.json(summary)
        return

    provenance = summary.get("provenance_summary") or {}
    actions = summary.get("recommended_actions") or []
    blockers = summary.get("blockers") or []
    warnings = summary.get("warnings") or []
    claims = summary.get("claims_requiring_confirmation") or []
    gap_risk_items = summary.get("gap_risk_items") or []
    selected_evidence = summary.get("selected_evidence") or []

    risk_level = str(summary.get("risk_level") or "").strip().lower()
    confidence_level = str(provenance.get("confidence_level") or "").strip().lower()
    ready = bool(summary.get("ready"))

    st.markdown(f"### {entity_label}")
    st.caption(
        f"{ENTITY_TYPE_LABELS.get(entity_type, entity_type)} · {entity_id} · "
        f"требуется ручная проверка={summary.get('requires_human_review', True)}"
    )

    col_risk, col_ready, col_review, col_confidence = st.columns(4)
    with col_risk:
        st.metric("Риск", _format_label(risk_level, RISK_LEVEL_LABELS))
    with col_ready:
        st.metric("Готово", "Да" if ready else "Нет")
    with col_review:
        st.metric(
            "Человеческая проверка",
            "Требуется" if summary.get("requires_human_review", True) else "Не требуется",
        )
    with col_confidence:
        st.metric("Уверенность", _format_confidence_value(provenance))

    st.markdown("### Статусные бейджи")
    _render_inline_badges(
        [
            (f"Риск: {_format_label(risk_level, RISK_LEVEL_LABELS)}", _risk_badge_tone(risk_level)),
            ("Готово" if ready else "Блокировка", "success" if ready else "blocker"),
            (
                "Требуется ручная проверка" if summary.get("requires_human_review", True) else "Ручная проверка не требуется",
                "warning" if summary.get("requires_human_review", True) else "success",
            ),
            (
                _format_confidence_value(provenance),
                _confidence_badge_tone(confidence_level),
            ),
        ]
    )

    st.divider()

    if ready and not blockers and not warnings and not claims and not gap_risk_items:
        st.success(
            _translate_trust_text(
                "No blockers detected. All critical claims confirmed. Interview prep readiness acceptable."
            )
        )
    else:
        col_left, col_right = st.columns(2)
        with col_left:
            if blockers:
                _render_trust_panel_list("Blockers", [str(item) for item in blockers if str(item).strip()])
            else:
                st.success(_translate_trust_text("No blockers detected."))

            if warnings:
                st.markdown("---")
                _render_trust_panel_list("Warnings", [str(item) for item in warnings if str(item).strip()])
            else:
                st.success(_translate_trust_text("No warnings detected."))

        with col_right:
            if claims:
                _render_trust_panel_list(
                    "Claims requiring confirmation",
                    [
                        str(
                            item.get("text")
                            or item.get("claim_text")
                            or item.get("title")
                            or item.get("message")
                            or "Claim"
                        )
                        for item in claims
                        if isinstance(item, dict)
                    ],
                )
            else:
                st.success(_translate_trust_text("All critical claims confirmed."))

            if gap_risk_items:
                st.markdown("---")
                _render_trust_panel_list(
                    "Gap-risk items",
                    [
                        str(item.get("message") or item.get("keyword") or item.get("question_id") or "Gap risk")
                        for item in gap_risk_items
                        if isinstance(item, dict)
                    ],
                )
            else:
                st.success(_translate_trust_text("Interview prep readiness acceptable."))

    st.divider()
    st.markdown("### Выбранные доказательства")
    if not selected_evidence:
        st.caption(_translate_trust_text("No selected evidence was returned by the backend."))
    else:
        evidence_rows = []
        for item in selected_evidence:
            if not isinstance(item, dict):
                continue
            evidence_rows.append(
                {
                    "ID": item.get("id") or "—",
                    "Заголовок": item.get("title") or "—",
                    "Источник": item.get("source_type") or "—",
                    "Статус факта": item.get("fact_status") or "—",
                    "Причина": item.get("reason") or "—",
                }
            )
        if evidence_rows:
            st.dataframe(evidence_rows, width="stretch", hide_index=True)

    st.divider()
    st.markdown("### Рекомендованные действия")
    _render_grouped_actions([item for item in actions if isinstance(item, dict)])

    with st.expander(_translate_trust_text("Show evidence provenance"), expanded=False):
        _render_provenance_summary(provenance)



DEMO_UI_TEXT_REPLACEMENTS = {
    "Backend Developer": "Backend-разработчик",
    "Test Company": "Тестовая компания",
    "Remote": "Удалённо",
    "I am interested in this role because it matches my Python and backend development direction.": (
        "Меня интересует эта роль, потому что она соответствует моему направлению: "
        "Python и backend-разработка."
    ),
    "Situation: I worked on a practical Python project. Task: build a working prototype. Action: I implemented the backend flow. Result: the prototype was ready for review.": (
        "Ситуация: я работал над практическим Python-проектом. "
        "Задача: собрать рабочий прототип. "
        "Действия: реализовал backend-flow. "
        "Результат: прототип был готов к проверке."
    ),
}


def localize_demo_ui_text(value: str | None) -> str:
    if value is None:
        return ""

    text = str(value)
    for source, target in DEMO_UI_TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)

    return text


def format_demo_display_text(value: str | None) -> str:
    text = localize_demo_ui_text(value).strip()
    return text or "—"



def init_session_state() -> None:
    if "source_file" not in st.session_state:
        st.session_state.source_file = None
    if "resume_import" not in st.session_state:
        st.session_state.resume_import = None
    if "structured_profile" not in st.session_state:
        st.session_state.structured_profile = None
    if "achievements" not in st.session_state:
        st.session_state.achievements = None
    if "vacancy" not in st.session_state:
        st.session_state.vacancy = None
    if "vacancy_analysis" not in st.session_state:
        st.session_state.vacancy_analysis = None
    if "generated_resume" not in st.session_state:
        st.session_state.generated_resume = None
    if "generated_cover_letter" not in st.session_state:
        st.session_state.generated_cover_letter = None
    if "approved_resume" not in st.session_state:
        st.session_state.approved_resume = None
    if "approved_cover_letter" not in st.session_state:
        st.session_state.approved_cover_letter = None
    if "application" not in st.session_state:
        st.session_state.application = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "trust_panel_entity_type" not in st.session_state:
        st.session_state.trust_panel_entity_type = "document"
    if "trust_panel_document_id" not in st.session_state:
        st.session_state.trust_panel_document_id = None
    if "trust_panel_interview_prep_id" not in st.session_state:
        st.session_state.trust_panel_interview_prep_id = None


def render_sidebar() -> tuple[str, CareerCopilotApiClient, str | None]:
    st.sidebar.header("Backend")

    api_base_url = st.sidebar.text_input(
        "Базовый URL API",
        value=os.getenv("CAREER_COPILOT_API_BASE_URL", DEFAULT_API_BASE_URL),
        help="Например: http://localhost:8000/api/v1",
    ).strip()

    client = CareerCopilotApiClient(api_base_url=api_base_url)
    token = st.session_state.get("auth_token")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔐 Авторизация")

    if not token:
        auth_mode = st.sidebar.radio(
            "Режим",
            options=["login", "register"],
            horizontal=True,
            format_func=lambda value: "Вход" if value == "login" else "Регистрация",
            key="auth_mode",
        )

        demo_email = os.getenv("DEMO_EMAIL", "demo.candidate@example.com")
        demo_password = os.getenv("DEMO_PASSWORD", "DemoPass123!")

        default_email = demo_email if auth_mode == "login" else ""
        default_password = demo_password if auth_mode == "login" else ""

        email = st.sidebar.text_input(
            "Email",
            value=default_email,
            key=f"auth_email_{auth_mode}",
        )
        password = st.sidebar.text_input(
            "Пароль",
            value=default_password,
            type="password",
            key=f"auth_password_{auth_mode}",
        )

        if auth_mode == "register":
            password_confirm = st.sidebar.text_input(
                "Повторите пароль",
                value="",
                type="password",
                key="auth_password_confirm",
            )
        else:
            password_confirm = password

        if auth_mode == "login":
            button_label = "Войти"
            success_message = "✅ Авторизация успешна"
        else:
            button_label = "Зарегистрироваться"
            success_message = "✅ Пользователь зарегистрирован. Теперь можно войти."

        if st.sidebar.button(button_label, width="stretch", type="primary"):
            normalized_email = email.strip().lower()

            if not normalized_email:
                st.sidebar.error("Укажите email.")
            elif not password:
                st.sidebar.error("Укажите пароль.")
            elif auth_mode == "register" and password != password_confirm:
                st.sidebar.error("Пароли не совпадают.")
            else:
                try:
                    if auth_mode == "login":
                        result = client.login(normalized_email, password)
                        st.session_state.auth_token = result.get("access_token")
                        st.session_state.user_email = normalized_email
                        st.sidebar.success(success_message)
                        st.rerun()
                    else:
                        client.register(normalized_email, password)
                        st.sidebar.success(success_message)

                except httpx.HTTPStatusError as exc:
                    if auth_mode == "register" and exc.response.status_code == 409:
                        st.sidebar.error("Пользователь с таким email уже существует.")
                    elif auth_mode == "login" and exc.response.status_code == 401:
                        st.sidebar.error("Неверный email или пароль.")
                    else:
                        st.sidebar.error(f"Backend вернул HTTP {exc.response.status_code}")
                        st.sidebar.code(exc.response.text)
                except httpx.RequestError as exc:
                    st.sidebar.error("Не удалось подключиться к backend.")
                    st.sidebar.code(str(exc))
                except ValueError as exc:
                    st.sidebar.error("Backend вернул неожиданный ответ.")
                    st.sidebar.code(str(exc))
    else:
        st.sidebar.success(f"👤 {st.session_state.get('user_email', 'user')}")
        st.sidebar.caption(f"Токен активен до завершения сессии")
        if st.sidebar.button("Выйти", width="stretch"):
            st.session_state.pop("auth_token", None)
            st.session_state.pop("user_email", None)
            st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("Проверить соединение", width="stretch"):
        result = client.check_backend()
        if result.ok:
            st.sidebar.success("✅ Backend доступен")
        else:
            st.sidebar.error(f"❌ {result.error}")

    return api_base_url, client, token


def render_home() -> None:
    st.title("AI Career Copilot для HH")
    st.caption("Локальная операторская консоль для проверки MVP backend")

    st.markdown(
        """
Этот Streamlit-интерфейс намеренно сделан минимальным.

Текущий backend уже поддерживает полный MVP-сценарий:

- загрузка резюме;
- импорт резюме;
- извлечение структурированного профиля;
- извлечение достижений;
- импорт вакансии;
- анализ вакансии;
- генерация адаптированного резюме;
- генерация сопроводительного письма;
- подтверждение документов человеком;
- создание записи отклика;
- подготовка к собеседованию;
- Подготовка к интервью;
- сохранение ответов на вопросы интервью и базовая обратная связь.
"""
    )

    st.info(
        "Frontend подключает полный MVP-сценарий. "
        "Все внешние действия остаются human-in-the-loop: система не отправляет отклики автоматически."
    )


def render_resume_upload_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("1. Загрузка резюме")

    uploaded_file = st.file_uploader(
        "Выберите файл резюме",
        type=["txt", "pdf", "docx"],
        help="Для MVP поддерживаются TXT, PDF и DOCX.",
    )

    if uploaded_file is None:
        st.info("Выберите файл резюме, чтобы отправить его в backend.")
        return

    st.caption(f"Файл: {uploaded_file.name}")
    st.caption(f"Тип: {uploaded_file.type or 'не определён'}")
    st.caption(f"Размер: {uploaded_file.size} байт")

    if st.button("Загрузить резюме", type="primary", width="stretch"):
        try:
            result = client.upload_file(path="/files/upload",
                file_kind="resume",
                filename=uploaded_file.name,
                content=uploaded_file.getvalue(),
                content_type=uploaded_file.type or "application/octet-stream", token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        st.session_state.source_file = result
        st.session_state.resume_import = None
        st.session_state.structured_profile = None
        st.session_state.achievements = None
        st.session_state.vacancy = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Резюме загружено")

    if st.session_state.source_file:
        source_file = st.session_state.source_file

        st.markdown("### Загруженный файл")
        st.json(
            {
                "source_file_id": source_file.get("id"),
                "file_kind": source_file.get("file_kind"),
                "original_name": source_file.get("original_name"),
            }
        )


def render_resume_import_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("2. Импорт резюме")

    source_file = st.session_state.source_file
    if not source_file:
        st.info("Сначала загрузите файл резюме на шаге 1.")
        return

    source_file_id = source_file.get("id")
    if not source_file_id:
        st.error("В загруженном файле не найден source_file_id.")
        st.json(source_file)
        return

    st.caption(f"source_file_id: {source_file_id}")

    if st.button("Импортировать резюме", type="primary", width="stretch"):
        try:
            result = client.post_json("/profile/import-resume",
                {
                    "source_file_id": source_file_id,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.resume_import = result
        st.session_state.structured_profile = None
        st.session_state.achievements = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Резюме импортировано")

    if st.session_state.resume_import:
        resume_import = st.session_state.resume_import

        st.markdown("### Результат импорта")
        st.json(
            {
                "profile_id": resume_import.get("profile_id"),
                "source_file_id": resume_import.get("source_file_id"),
                "extraction_id": resume_import.get("extraction_id"),
                "status": resume_import.get("status"),
                "detected_format": resume_import.get("detected_format"),
                "text_length": resume_import.get("text_length"),
            }
        )

        text_preview = resume_import.get("text_preview")
        if text_preview:
            with st.expander("Предпросмотр извлечённого текста", expanded=False):
                st.text(text_preview)


def render_structured_profile_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("3. Извлечение структурированного профиля")

    resume_import = st.session_state.resume_import
    if not resume_import:
        st.info("Сначала импортируйте резюме на шаге 2.")
        return

    extraction_id = resume_import.get("extraction_id")
    if not extraction_id:
        st.error("В результате импорта не найден extraction_id.")
        st.json(resume_import)
        return

    st.caption(f"extraction_id: {extraction_id}")

    if st.button("Извлечь структурированный профиль", type="primary", width="stretch"):
        try:
            result = client.post_json("/profile/extract-structured",
                {
                    "extraction_id": extraction_id,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.structured_profile = result
        st.session_state.achievements = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Структурированный профиль извлечён")

    if st.session_state.structured_profile:
        profile = st.session_state.structured_profile
        warning_labels = {
            "contacts, achievements, metrics and proof-status mapping are not extracted in v1": (
                "В этой версии контакты, метрики и подтверждения фактов извлекаются частично. "
                "Проверьте достижения на следующем шаге."
            ),
        }

        st.markdown("### Структурированный профиль")

        col_left, col_right = st.columns(2)

        with col_left:
            st.text_input(
                "ФИО",
                value=profile.get("full_name") or "",
                disabled=True,
            )
            st.text_input(
                "Заголовок профиля",
                value=profile.get("headline") or "",
                disabled=True,
            )
            st.text_input(
                "Локация",
                value=profile.get("location") or "",
                disabled=True,
            )

        with col_right:
            st.metric(
                "Количество опытов работы",
                profile.get("experience_count", 0),
            )
            st.caption(f"profile_id: {profile.get('profile_id')}")
            st.caption(f"extraction_id: {profile.get('extraction_id')}")

        target_roles = profile.get("target_roles") or []
        if target_roles:
            st.markdown("#### Целевые роли")
            for role in target_roles:
                st.markdown(f"- {role}")

        warnings = profile.get("warnings") or []
        if warnings:
            st.markdown("#### Предупреждения")
            for warning in warnings:
                st.warning(warning_labels.get(str(warning), str(warning)))

        with st.expander("Технический JSON результата", expanded=False):
            st.json(profile)


def render_achievements_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("4. Извлечение достижений")

    resume_import = st.session_state.resume_import
    if not resume_import:
        st.info("Сначала импортируйте резюме на шаге 2.")
        return

    structured_profile = st.session_state.structured_profile
    if not structured_profile:
        st.info("Сначала извлеките структурированный профиль на шаге 3.")
        return

    extraction_id = resume_import.get("extraction_id")
    if not extraction_id:
        st.error("В результате импорта не найден extraction_id.")
        st.json(resume_import)
        return

    st.caption(f"extraction_id: {extraction_id}")

    if st.button("Извлечь достижения", type="primary", width="stretch"):
        try:
            result = client.post_json("/profile/extract-achievements",
                {
                    "extraction_id": extraction_id,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.achievements = result
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Достижения извлечены")

    if st.session_state.achievements:
        achievements_result = st.session_state.achievements

        st.markdown("### Извлечённые достижения")

        st.metric(
            "Количество достижений",
            achievements_result.get("achievement_count", 0),
        )

        st.caption(f"profile_id: {achievements_result.get('profile_id')}")
        st.caption(f"extraction_id: {achievements_result.get('extraction_id')}")

        achievements = achievements_result.get("achievements") or []
        if achievements:
            for index, achievement in enumerate(achievements, start=1):
                with st.container(border=True):
                    st.markdown(f"**{index}. {achievement.get('title', '')}**")
                    fact_status = achievement.get("fact_status")
                    if fact_status == "needs_confirmation":
                        st.warning("Требует подтверждения пользователем")
                    elif fact_status == "confirmed":
                        st.success("Подтверждено пользователем")
                    else:
                        st.caption(f"Статус факта: {fact_status}")


        if achievements:
            st.markdown("#### Проверка достижений перед документами")

            unconfirmed_achievements = [
                item for item in achievements if item.get("fact_status") != "confirmed"
            ]

            if unconfirmed_achievements:
                st.warning(
                    "Проверьте формулировки достижений перед импортом вакансии. "
                    "Шаг 5 разблокируется только когда все достижения будут confirmed."
                )
            else:
                st.success("Все извлечённые достижения подтверждены.")

            reviewed_items: list[dict] = []

            with st.form("achievement_review_form"):
                for index, achievement in enumerate(achievements, start=1):
                    achievement_id = achievement.get("id")
                    title = achievement.get("title") or ""
                    fact_status = achievement.get("fact_status") or "needs_confirmation"
                    evidence_note = achievement.get("evidence_note") or ""

                    with st.container(border=True):
                        st.markdown(f"#### Достижение {index}")

                        if not achievement_id:
                            st.error(
                                "Backend не вернул id достижения. "
                                "Повторите извлечение достижений после обновления backend."
                            )

                        edited_title = st.text_area(
                            "Текст достижения",
                            value=title,
                            height=90,
                            key=f"achievement_title_{achievement_id or index}",
                        )

                        status_options = ["needs_confirmation", "confirmed"]
                        status_labels = {
                            "needs_confirmation": "Требует подтверждения",
                            "confirmed": "Подтверждено",
                        }
                        status_index = (
                            status_options.index(fact_status)
                            if fact_status in status_options
                            else 0
                        )

                        edited_fact_status = st.selectbox(
                            "Статус факта",
                            options=status_options,
                            index=status_index,
                            key=f"achievement_status_{achievement_id or index}",
                            format_func=lambda value: status_labels.get(value, value),
                            help=(
                                "«Подтверждено» — пользователь проверил факт, и его можно использовать в документах. "
                                "«Требует подтверждения» — факт пока нельзя использовать как сильное утверждение."
                            ),
                        )

                        edited_evidence_note = st.text_area(
                            "Заметка / источник подтверждения",
                            value=evidence_note,
                            height=80,
                            key=f"achievement_evidence_{achievement_id or index}",
                        )

                        if edited_fact_status == "confirmed":
                            st.success("Это достижение будет считаться подтверждённым.")
                        else:
                            st.warning("Это достижение останется неподтверждённым.")

                        reviewed_items.append(
                            {
                                "id": achievement_id,
                                "title": edited_title,
                                "fact_status": edited_fact_status,
                                "evidence_note": edited_evidence_note,
                            }
                        )

                submitted_review = st.form_submit_button(
                    "Сохранить проверку достижений",
                    type="primary",
                    width="stretch",
                )

            if submitted_review:
                invalid_items = [
                    item
                    for item in reviewed_items
                    if not item.get("id") or not str(item.get("title") or "").strip()
                ]

                if invalid_items:
                    st.error("У всех достижений должен быть id и непустой текст.")
                    return

                try:
                    updated_items: list[dict] = []

                    for item in reviewed_items:
                        result = client.patch_json(f"/profile/achievements/{item['id']}/review",
                            {
                                "title": str(item["title"]).strip(),
                                "fact_status": item["fact_status"],
                                "evidence_note": str(item.get("evidence_note") or "").strip()
                                or None,
                            }, token=token)

                        if not isinstance(result, dict):
                            st.error("Backend вернул неожиданный формат ответа")
                            st.json(result)
                            return

                        updated_items.append(result)

                except httpx.HTTPStatusError as exc:
                    st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
                    st.code(exc.response.text)
                    return
                except httpx.RequestError as exc:
                    st.error("Не удалось подключиться к backend")
                    st.code(str(exc))
                    return
                except ValueError as exc:
                    st.error("Backend вернул неожиданный ответ")
                    st.code(str(exc))
                    return

                st.session_state.achievements = {
                    **achievements_result,
                    "achievement_count": len(updated_items),
                    "achievements": updated_items,
                }
                st.session_state.vacancy_analysis = None
                st.session_state.generated_resume = None
                st.session_state.generated_cover_letter = None
                st.session_state.approved_resume = None
                st.session_state.approved_cover_letter = None
                st.session_state.application = None

                st.success("Проверка достижений сохранена")
                st.rerun()

        warnings = achievements_result.get("warnings") or []
        if warnings:
            st.markdown("#### Предупреждения")
            for warning in warnings:
                st.warning(warning)

        with st.expander("Технический JSON результата", expanded=False):
            st.json(achievements_result)


def render_vacancy_import_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("5. Импорт вакансии")

    achievements = st.session_state.achievements
    if not achievements:
        st.info("Сначала извлеките достижения на шаге 4.")
        return

    achievement_items = achievements.get("achievements") or []
    unconfirmed_achievements = [
        item for item in achievement_items if item.get("fact_status") != "confirmed"
    ]

    if unconfirmed_achievements:
        st.info(
            "Перед импортом вакансии подтвердите достижения на шаге 4. "
            "Это защищает pipeline от использования неподтверждённого опыта в документах."
        )
        return

    st.markdown("#### Быстрый импорт по ссылке HH")

    hh_source_url = st.text_input(
        "Ссылка на вакансию HH",
        value="",
        placeholder="https://barnaul.hh.ru/vacancy/133412268",
        key="hh_vacancy_import_url",
    )

    if st.button("Загрузить вакансию по ссылке HH", type="primary", width="stretch"):
        if not hh_source_url.strip():
            st.error("Вставьте ссылку на вакансию HH.")
        else:
            try:
                result = client.import_vacancy_from_url(
                    source_url=hh_source_url.strip(),
                    token=token,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 502:
                    st.warning(
                        "HH не отдал вакансию по API. "
                        "Скопируйте текст вакансии и вставьте его в ручную форму ниже."
                    )
                else:
                    st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
                    st.code(exc.response.text)
            except httpx.RequestError as exc:
                st.error("Не удалось подключиться к backend")
                st.code(str(exc))
            except ValueError as exc:
                st.error("Backend вернул неожиданный ответ")
                st.code(str(exc))
            else:
                if not isinstance(result, dict):
                    st.error("Backend вернул неожиданный формат ответа")
                    st.json(result)
                else:
                    st.session_state.vacancy = result
                    st.session_state.vacancy_analysis = None
                    st.session_state.generated_resume = None
                    st.session_state.generated_cover_letter = None
                    st.session_state.approved_resume = None
                    st.session_state.approved_cover_letter = None
                    st.session_state.application = None
                    st.success("Вакансия загружена по ссылке HH")
                    st.rerun()

    st.divider()
    st.markdown("#### Ручной импорт")

    default_description = """Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker
"""

    use_demo_vacancy = st.checkbox(
        "Заполнить демо-вакансией",
        value=False,
        help="Используйте только для проверки demo-flow.",
    )

    with st.form("vacancy_import_form"):
        title_default = "Backend-разработчик" if use_demo_vacancy else ""
        company_default = "Тестовая компания" if use_demo_vacancy else ""
        location_default = "Удалённо" if use_demo_vacancy else ""
        description_default = default_description if use_demo_vacancy else ""

        title = st.text_input(
            "Название вакансии",
            value=title_default,
        )
        company = st.text_input(
            "Компания",
            value=company_default,
        )
        location = st.text_input(
            "Локация",
            value=location_default,
        )
        source_url = st.text_input(
            "Ссылка на вакансию",
            value="",
            help="Опционально. Для MVP можно оставить пустым.",
        )
        description_raw = st.text_area(
            "Текст вакансии",
            value=description_default,
            height=220,
            help="Вставьте требования и описание вакансии вручную.",
        )

        submitted = st.form_submit_button(
            "Импортировать вакансию",
            type="primary",
            width="stretch",
        )

    if submitted:
        if not description_raw.strip() and not source_url.strip():
            st.error("Нужно указать текст вакансии или ссылку на вакансию.")
            return

        payload = {
            "source": "manual",
            "source_url": source_url.strip() or None,
            "title": title.strip() or None,
            "company": company.strip() or None,
            "location": location.strip() or None,
            "description_raw": description_raw.strip() or None,
        }

        try:
            result = client.post_json("/vacancies/import",
                payload, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.vacancy = result
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Вакансия импортирована")

    if st.session_state.vacancy:
        vacancy = st.session_state.vacancy

        st.markdown("### Импортированная вакансия")
        st.json(
            {
                "vacancy_id": vacancy.get("vacancy_id"),
                "id": vacancy.get("id"),
                "source": vacancy.get("source"),
                "source_url": vacancy.get("source_url"),
                "title": vacancy.get("title"),
                "company": vacancy.get("company"),
                "location": vacancy.get("location"),
                "description_length": vacancy.get("description_length"),
            }
        )


def render_vacancy_analysis_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("6. Анализ вакансии")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")

    if st.button("Проанализировать вакансию", type="primary", width="stretch"):
        try:
            result = client.post_json(f"/vacancies/{vacancy_id}/analyze",
                {}, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.vacancy_analysis = result
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Вакансия проанализирована")

    if st.session_state.vacancy_analysis:
        analysis = st.session_state.vacancy_analysis

        st.markdown("### Результат анализа")

        col_left, col_right, col_center = st.columns(3)

        with col_left:
            st.metric("Match score", analysis.get("match_score"))

        with col_center:
            st.metric("Must-have", len(analysis.get("must_have") or []))

        with col_right:
            st.metric("Nice-to-have", len(analysis.get("nice_to_have") or []))

        st.caption(f"analysis_id: {analysis.get('analysis_id')}")
        st.caption(f"analysis_version: {analysis.get('analysis_version')}")

        must_have = analysis.get("must_have") or []
        nice_to_have = analysis.get("nice_to_have") or []
        strengths = analysis.get("strengths") or []
        gaps = analysis.get("gaps") or []

        col_must, col_nice = st.columns(2)

        with col_must:
            st.markdown("#### Must-have требования")
            if must_have:
                for item in must_have:
                    st.markdown(f"- {item.get('text', item)}")
            else:
                st.caption("Не найдено")

        with col_nice:
            st.markdown("#### Nice-to-have требования")
            if nice_to_have:
                for item in nice_to_have:
                    st.markdown(f"- {item.get('text', item)}")
            else:
                st.caption("Не найдено")

        col_strengths, col_gaps = st.columns(2)

        with col_strengths:
            st.markdown("#### Сильные совпадения")
            if strengths:
                for item in strengths:
                    keyword = item.get("keyword")
                    scope = item.get("scope")
                    weight = item.get("weight")
                    evidence = item.get("evidence")
                    st.success(f"{keyword} / {scope} / weight={weight}")
                    if evidence:
                        st.caption(f"evidence: {evidence}")
            else:
                st.caption("Совпадений не найдено")

        with col_gaps:
            st.markdown("#### Gap-зоны")
            if gaps:
                for item in gaps:
                    keyword = item.get("keyword")
                    scope = item.get("scope")
                    weight = item.get("weight")
                    reason = item.get("reason")
                    st.warning(f"{keyword} / {scope} / weight={weight}")
                    if reason:
                        st.caption(f"reason: {reason}")
            else:
                st.caption("Критичных gaps не найдено")

        keywords = analysis.get("keywords") or []
        if keywords:
            with st.expander("Ключевые слова", expanded=False):
                st.write(", ".join(keywords))

        with st.expander("Технический JSON результата", expanded=False):
            st.json(analysis)

    if vacancy_id:
        st.divider()
        _render_vacancy_intelligence_block(client, vacancy_id=str(vacancy_id), token=token)


def _render_vacancy_intelligence_block(
    client: CareerCopilotApiClient,
    *,
    vacancy_id: str,
    token: str | None = None,
) -> None:
    st.markdown("### Анализ вакансии")
    st.caption("Детерминированный разбор соответствия для операционных подсказок, а не вероятность найма.")

    try:
        fit = client.get_vacancy_fit(vacancy_id, token=token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 404}:
            st.info("Анализ вакансии доступен после анализа вакансии и извлечения профиля.")
        else:
            st.warning(f"Анализ вакансии недоступен: HTTP {exc.response.status_code}")
            st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.warning("Не удалось подключиться к backend для анализа вакансии.")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.warning("Анализ вакансии вернул неожиданный ответ.")
        st.code(str(exc))
        return

    if not isinstance(fit, dict):
        st.warning("Анализ вакансии вернул неожиданный payload.")
        st.json(fit)
        return

    recommendation = str(fit.get("readiness_recommendation") or "—")
    gap_severity = str(fit.get("gap_severity") or "—")

    if recommendation == "Ready to apply":
        st.success("Готово к отклику")
    elif recommendation == "Apply with caution":
        st.warning("Отклик с осторожностью")
    else:
        st.error("Требует доработки")

    col_overall, col_skills, col_evidence, col_experience, col_leadership = st.columns(5)
    with col_overall:
        st.metric("Общий fit", fit.get("overall_fit_score", 0))
    with col_skills:
        st.metric("Навыки", fit.get("skills_fit", 0))
    with col_evidence:
        st.metric("Доказательства", fit.get("evidence_fit", 0))
    with col_experience:
        st.metric("Опыт", fit.get("experience_fit", 0))
    with col_leadership:
        st.metric("Лидерство", fit.get("leadership_fit", 0))

    st.caption(f"Серьёзность пробелов: {gap_severity}")
    if fit.get("analysis_version"):
        st.caption(f"Версия анализа: {fit.get('analysis_version')}")

    coverage = fit.get("evidence_coverage") or {}
    required = coverage.get("required") or []
    if required:
        st.markdown("#### Эта вакансия требует")
        for item in required:
            st.markdown(f"- {item}")

    def _render_coverage_group(label: str, items: list[dict[str, object]], kind: str) -> None:
        st.markdown(f"#### {label}")
        if not items:
            st.caption("—")
            return

        for item in items:
            requirement = str(item.get("requirement") or "Requirement")
            reason = str(item.get("reason") or "—")
            scope = str(item.get("scope") or "—")
            severity = str(item.get("severity") or "—")
            evidence_ids = [str(value) for value in (item.get("evidence_ids") or []) if str(value).strip()]
            supporting_evidence = item.get("supporting_evidence") or []

            with st.container(border=True):
                if kind == "strong":
                    st.success(requirement)
                elif kind == "medium":
                    st.warning(requirement)
                else:
                    st.info(requirement)
                st.caption(f"scope: {scope} · severity: {severity}")
                st.caption(f"причина: {reason}")
                st.caption(
                    "evidence_ids: " + (", ".join(evidence_ids) if evidence_ids else "—")
                )

                if supporting_evidence:
                    with st.expander("Поддерживающие доказательства", expanded=False):
                        for evidence in supporting_evidence:
                            title = str(evidence.get("title") or "Evidence").strip()
                            evidence_id = str(evidence.get("evidence_id") or "").strip() or "—"
                            score = evidence.get("score")
                            fact_status = str(evidence.get("fact_status") or "—")
                            evidence_strength = str(evidence.get("evidence_strength") or "—")
                            st.markdown(f"**{title}**")
                            st.caption(f"evidence_id: {evidence_id}")
                            st.caption(
                                f"оценка: {round(float(score)) if score is not None else '—'} · "
                                f"статус факта: {fact_status} · сила: {evidence_strength}"
                            )
                            star_preview = evidence.get("star_preview") or {}
                            if isinstance(star_preview, dict) and star_preview:
                                st.caption(
                                    "STAR-превью: "
                                    + ", ".join(
                                        f"{key}={value}"
                                        for key, value in star_preview.items()
                                        if value not in (None, "", [])
                                    )
                                )
                            snippet_text = str(evidence.get("snippet_text") or "").strip()
                            if snippet_text:
                                st.write(snippet_text)

    _render_coverage_group("Сильные доказательства", coverage.get("strong") or [], "strong")
    _render_coverage_group("Средние доказательства", coverage.get("medium") or [], "medium")
    _render_coverage_group("Без подтверждённых доказательств", coverage.get("missing") or [], "missing")


def render_resume_generation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("7. Генерация адаптированного резюме")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_analysis = st.session_state.vacancy_analysis
    if not vacancy_analysis:
        st.info("Сначала проанализируйте вакансию на шаге 6.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")

    match_score = vacancy_analysis.get("match_score")
    if match_score is not None:
        st.metric("Match score перед генерацией", match_score)

    st.warning(
        "Резюме будет создано как draft. Перед использованием его нужно проверить и подтвердить человеком."
    )

    if st.button("Сгенерировать адаптированное резюме", type="primary", width="stretch"):
        try:
            result = client.post_json("/documents/resumes/generate",
                {
                    "vacancy_id": vacancy_id,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.generated_resume = result
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Адаптированное резюме сгенерировано")

    if st.session_state.generated_resume:
        resume = st.session_state.generated_resume

        st.markdown("### Сгенерированное резюме")
        st.json(
            {
                "document_id": resume.get("document_id"),
                "vacancy_id": resume.get("vacancy_id"),
                "review_status": resume.get("review_status"),
                "version_label": resume.get("version_label"),
                "created_at": resume.get("created_at"),
            }
        )

        preview = resume.get("rendered_text_preview")
        if preview:
            st.markdown("#### Предпросмотр")
            st.text_area(
                "Текст резюме",
                value=preview,
                height=420,
                disabled=True,
            )

        review_status = resume.get("review_status")
        if review_status == "draft":
            st.info("Статус документа: draft. Следующий шаг — проверка и подтверждение.")


def render_cover_letter_generation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("8. Генерация сопроводительного письма")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_analysis = st.session_state.vacancy_analysis
    if not vacancy_analysis:
        st.info("Сначала проанализируйте вакансию на шаге 6.")
        return

    generated_resume = st.session_state.generated_resume
    if not generated_resume:
        st.info("Сначала сгенерируйте адаптированное резюме на шаге 7.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")

    match_score = vacancy_analysis.get("match_score")
    if match_score is not None:
        st.metric("Match score перед генерацией письма", match_score)

    st.warning(
        "Письмо будет создано как draft. Перед отправкой его нужно проверить и подтвердить человеком."
    )

    if st.button(
        "Сгенерировать сопроводительное письмо",
        type="primary",
        width="stretch",
    ):
        try:
            result = client.post_json("/documents/letters/generate",
                {
                    "vacancy_id": vacancy_id,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.generated_cover_letter = result
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Сопроводительное письмо сгенерировано")

    if st.session_state.generated_cover_letter:
        letter = st.session_state.generated_cover_letter

        st.markdown("### Сгенерированное сопроводительное письмо")
        st.json(
            {
                "document_id": letter.get("document_id"),
                "vacancy_id": letter.get("vacancy_id"),
                "review_status": letter.get("review_status"),
                "version_label": letter.get("version_label"),
                "created_at": letter.get("created_at"),
            }
        )

        preview = letter.get("rendered_text_preview")
        if preview:
            st.markdown("#### Предпросмотр")
            st.text_area(
                "Текст письма",
                value=preview,
                height=360,
                disabled=True,
            )

        # ---------------------------------------------------------
        # Блок: что было адаптировано в письме (gap-mitigation)
        # ---------------------------------------------------------
        with st.expander("📋 Что было адаптировано под эту вакансию", expanded=False):
            st.markdown("Письмо усилено следующими элементами:")
            matched = [s.get("keyword") for s in (vacancy_analysis.get("strengths") or []) if s.get("keyword")]
            gaps = [g.get("keyword") for g in (vacancy_analysis.get("gaps") or []) if g.get("keyword")]
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("✅ **Усилено** (есть в профиле + в вакансии)")
                for kw in matched[:5]:
                    st.markdown(f"- {kw}")
            with col2:
                st.markdown("💡 **Проактивно закрыто** (есть в вакансии, добавлен контекст)")
                for kw in gaps[:5]:
                    st.markdown(f"- {kw}")
            st.caption("Письмо не дублирует резюме, а объясняет мотивацию и релевантность.")

        review_status = letter.get("review_status")
        if review_status == "draft":
            st.info("Статус документа: draft. Следующий шаг — проверка и подтверждение.")


def render_document_approval_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("9. Проверка и подтверждение документов")
    render_document_review_workspace_tab(
        client,
        token=token,
        selection_state_key="document_review_workspace_step9_selection",
    )


def render_application_creation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("10. Создание записи отклика")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    approved_resume = st.session_state.approved_resume
    if not approved_resume:
        st.info("Сначала подтвердите резюме на шаге 9.")
        return

    approved_cover_letter = st.session_state.approved_cover_letter
    if not approved_cover_letter:
        st.info("Сначала подтвердите сопроводительное письмо на шаге 9.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    resume_document_id = approved_resume.get("document_id")
    cover_letter_document_id = approved_cover_letter.get("document_id")

    if not resume_document_id:
        st.error("В подтверждённом резюме не найден document_id.")
        st.json(approved_resume)
        return

    if not cover_letter_document_id:
        st.error("В подтверждённом письме не найден document_id.")
        st.json(approved_cover_letter)
        return

    if approved_resume.get("review_status") != "approved" or not approved_resume.get("is_active"):
        st.warning("Резюме ещё не подтверждено или не активно.")
        return

    if (
        approved_cover_letter.get("review_status") != "approved"
        or not approved_cover_letter.get("is_active")
    ):
        st.warning("Сопроводительное письмо ещё не подтверждено или не активно.")
        return

    st.caption(f"vacancy_id: {vacancy_id}")
    st.caption(f"resume_document_id: {resume_document_id}")
    st.caption(f"cover_letter_document_id: {cover_letter_document_id}")

    st.warning(
        "Будет создана только внутренняя запись отклика в статусе draft. "
        "Автоматическая отправка на HH или другую площадку не выполняется."
    )

    notes = st.text_area(
        "Заметка к отклику",
        value="Создано через Streamlit UI. Отклик ещё не отправлен.",
        height=90,
    )

    if st.button("Создать запись отклика", type="primary", width="stretch"):
        try:
            result = client.post_json("/applications",
                {
                    "vacancy_id": vacancy_id,
                    "resume_document_id": resume_document_id,
                    "cover_letter_document_id": cover_letter_document_id,
                    "notes": notes.strip() or None,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                st.warning("Отклик для этой вакансии уже существует. Дубликат не создан.")
                st.code(exc.response.text)
                return

            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.application = result
        st.success("Запись отклика создана")

    if st.session_state.application:
        application = st.session_state.application

        st.markdown("### Созданная запись отклика")
        st.json(
            {
                "application_id": application.get("id"),
                "vacancy_id": application.get("vacancy_id"),
                "resume_document_id": application.get("resume_document_id"),
                "cover_letter_document_id": application.get("cover_letter_document_id"),
                "status": application.get("status"),
                "source": application.get("source"),
                "applied_at": application.get("applied_at"),
                "notes": application.get("notes"),
                "created_at": application.get("created_at"),
            }
        )

        if application.get("status") == "draft":
            st.info(
                "Отклик создан в статусе draft. Это не означает отправку. "
                "После ручной отправки на HH статус можно будет изменить на applied отдельным шагом."
            )


def render_application_status_update_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("11. Отметка ручной отправки отклика")

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    application_id = application.get("id")
    if not application_id:
        st.error("В записи отклика не найден application_id.")
        st.json(application)
        return

    current_status = application.get("status")
    st.caption(f"application_id: {application_id}")
    st.caption(f"current_status: {current_status}")

    try:
        workflow = client.get_json(f"/applications/{application_id}/workflow", token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ")
        st.code(str(exc))
        return

    if not isinstance(workflow, dict):
        st.error("Backend вернул неожиданный формат workflow metadata")
        st.json(workflow)
        return

    if current_status == "applied":
        st.success("Отклик уже отмечен как отправленный.")
        st.json(
            {
                "application_id": application.get("id"),
                "status": application.get("status"),
                "applied_at": application.get("applied_at"),
                "notes": application.get("notes"),
            }
        )
        return

    if not workflow.get("can_submit"):
        st.info(
            "Ручная отметка отправки недоступна для текущего статуса. "
            "Backend сам определяет, когда submit доступен."
        )
        with st.expander("Метаданные workflow", expanded=False):
            st.json(workflow)
        return

    st.warning(
        "Нажимайте эту кнопку только после того, как вы вручную отправили отклик на HH "
        "или другой площадке. Система сама ничего не отправляет."
    )

    external_link = st.text_input(
        "Ссылка на отклик",
        value=application.get("external_link") or "",
        help="Опционально. Можно вставить ссылку на HH или другую площадку.",
    )

    if st.button(
        "Отметить как отправленный вручную",
        type="primary",
        width="stretch",
    ):
        try:
            result = client.post_json(f"/applications/{application_id}/submit",
                {
                    "source": "manual",
                    "external_link": external_link.strip() or None,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(result, dict):
            st.error("Backend вернул неожиданный формат ответа")
            st.json(result)
            return

        st.session_state.application = result
        st.success("Отклик отмечен как отправленный")

    if st.session_state.application:
        updated_application = st.session_state.application

        st.markdown("### Текущий статус отклика")
        st.json(
            {
                "application_id": updated_application.get("id"),
                "vacancy_id": updated_application.get("vacancy_id"),
                "status": updated_application.get("status"),
                "applied_at": updated_application.get("applied_at"),
                "notes": updated_application.get("notes"),
                "updated_at": updated_application.get("updated_at"),
            }
        )


def render_interview_preparation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("13. Подготовка к интервью")
    st.caption(
        "Новый deterministic prep-слой вынесен в отдельный workspace. "
        "Здесь остался короткий вход без дублирования логики ответов на mock interview."
    )

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    if application.get("status") != "applied":
        st.info(
            "Interview prep имеет смысл запускать после ручной отправки отклика "
            "и перевода статуса в applied на шаге 11."
        )
        return

    st.caption(f"application_id: {application.get('id')}")
    st.caption(f"vacancy_id: {application.get('vacancy_id')}")

    render_interview_prep_workspace_tab(
        client,
        token=token,
        selection_state_key="interview_prep_workspace_flow_selection",
    )


def render_application_dashboard(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("Дашборд откликов")
    st.caption(
        "Список внутренних записей откликов. Это не отправляет отклики на HH и не выполняет внешних действий."
    )

    if not token:
        st.warning("Войдите, чтобы открыть дашборд откликов.")
        return

    status_labels = {
        "draft": "Черновик",
        "ready": "Готов к отправке",
        "applied": "Отправлен вручную",
        "screening": "Скрининг",
        "interview": "Интервью",
        "rejected": "Отказ",
        "offer": "Оффер",
        "withdrawn": "Отозван",
    }

    try:
        applications = client.get_json("/applications", token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ")
        st.code(str(exc))
        return

    if not isinstance(applications, list):
        st.error("Backend вернул неожиданный формат списка откликов")
        st.json(applications)
        return

    if not applications:
        st.info("Пока нет созданных откликов.")
        return

    applications_by_id = {
        str(application.get("id")): application
        for application in applications
        if application.get("id")
    }

    try:
        reminders = client.get_application_reminders(token=token)
    except Exception:
        reminders = None

    if isinstance(reminders, list) and reminders:
        reminder_counts: dict[str, int] = {}
        for reminder in reminders:
            reminder_type = str(reminder.get("reminder_type") or "unknown")
            reminder_counts[reminder_type] = reminder_counts.get(reminder_type, 0) + 1

        st.warning("⚠ Требует внимания")

        for reminder_type, count in reminder_counts.items():
            if reminder_type == "follow_up_missing":
                st.markdown(f"- {count} откликов ждут follow-up больше 14 дней")
            elif reminder_type == "ready_not_submitted":
                st.markdown(f"- {count} готовых откликов не отправлены")
            elif reminder_type == "draft_stale":
                st.markdown(f"- {count} черновиков без активности")
            else:
                label = APPLICATION_REMINDER_LABELS.get(reminder_type, reminder_type)
                st.markdown(f"- {count} {label.lower()}")

        reminder_rows = []
        for reminder in reminders:
            application_id = str(reminder.get("application_id") or "")
            application = applications_by_id.get(application_id, {})
            reminder_rows.append(
                {
                    "Тип": APPLICATION_REMINDER_LABELS.get(
                        str(reminder.get("reminder_type") or ""),
                        str(reminder.get("reminder_type") or ""),
                    ),
                    "Вакансия": format_vacancy_title(application.get("vacancy_title")),
                    "Возраст": f"{reminder.get('days_since_event', 0)}d",
                }
            )

        st.dataframe(
            reminder_rows,
            use_container_width=True,
            hide_index=True,
        )

    try:
        analytics = client.get_json("/applications/analytics/summary", token=token)
    except Exception:
        analytics = None

    if isinstance(analytics, dict):
        col_total, col_applied, col_conversion, col_avg, col_offer, col_rejected = st.columns(6)

        with col_total:
            st.metric("Всего откликов", analytics.get("total_applications", 0))

        with col_applied:
            count_by_status = analytics.get("count_by_status") or {}
            st.metric(
                "Отправлены+",
                sum(
                    count_by_status.get(status, 0)
                    for status in [
                        "applied",
                        "screening",
                        "interview",
                        "offer",
                        "rejected",
                        "withdrawn",
                    ]
                ),
            )

        with col_conversion:
            conversion_to_applied = analytics.get("conversion_to_applied") or 0
            st.metric("Конверсия в applied", f"{round(conversion_to_applied * 100)}%")

        with col_avg:
            avg = analytics.get("average_time_to_apply_hours")
            st.metric("Среднее время до отклика", f"{avg}h" if avg is not None else "—")

        with col_offer:
            st.metric("Офферы", analytics.get("offers_count", 0))

        with col_rejected:
            st.metric("Отказы", analytics.get("rejections_count", 0))

    counts_by_status = {
        "draft": 0,
        "ready": 0,
        "applied": 0,
        "screening": 0,
        "interview": 0,
        "rejected": 0,
        "offer": 0,
        "withdrawn": 0,
    }

    for application in applications:
        status_value = application.get("status")
        if status_value in counts_by_status:
            counts_by_status[status_value] += 1

    metric_cols = st.columns(8)

    for col, status_value in zip(metric_cols, counts_by_status.keys()):
        with col:
            st.metric(
                status_labels.get(status_value, status_value),
                counts_by_status[status_value],
            )

    table_rows = []
    for application in applications:
        status_value = application.get("status")
        table_rows.append(
            {
                "Вакансия": format_vacancy_title(application.get("vacancy_title")),
                "Компания": format_vacancy_company(application.get("vacancy_company")),
                "Локация": format_vacancy_location(application.get("vacancy_location")),
                "Статус": format_application_status(status_value),
                "Дата отправки": format_optional_datetime(application.get("applied_at")),
                "Результат": format_application_outcome(application.get("outcome")),
                "Создано": format_optional_datetime(application.get("created_at")),
                "Заметки": application.get("notes") or "—",
            }
        )

    st.markdown("### Список откликов")
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
    )

    application_ids = [
        str(application.get("id"))
        for application in applications
        if application.get("id")
    ]

    if not application_ids:
        st.warning("В списке откликов нет корректных application_id.")
        return

    applications_by_id = {
        str(application.get("id")): application
        for application in applications
        if application.get("id")
    }

    selected_application_id = st.selectbox(
        "Выберите отклик для просмотра и обновления статуса",
        options=application_ids,
        format_func=lambda value: (
            f"{status_labels.get(applications_by_id[value].get('status'), applications_by_id[value].get('status'))} "
            f"· {value[:8]} "
            f"· {applications_by_id[value].get('created_at') or ''}"
        ),
    )

    if not selected_application_id:
        return

    try:
        selected_application = client.get_json(f"/applications/{selected_application_id}", token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ")
        st.code(str(exc))
        return

    if not isinstance(selected_application, dict):
        st.error("Backend вернул неожиданный формат отклика")
        st.json(selected_application)
        return

    st.markdown("### Детали отклика")
    st.json(
        {
            "application_id": selected_application.get("id"),
            "vacancy_id": selected_application.get("vacancy_id"),
            "resume_document_id": selected_application.get("resume_document_id"),
            "cover_letter_document_id": selected_application.get("cover_letter_document_id"),
            "status": selected_application.get("status"),
            "source": selected_application.get("source"),
            "applied_at": selected_application.get("applied_at"),
            "outcome": selected_application.get("outcome"),
            "notes": selected_application.get("notes"),
            "created_at": selected_application.get("created_at"),
            "updated_at": selected_application.get("updated_at"),
        }
    )

    vacancy_id_for_fit = str(selected_application.get("vacancy_id") or "").strip()
    if vacancy_id_for_fit:
        st.divider()
        _render_vacancy_intelligence_block(client, vacancy_id=vacancy_id_for_fit, token=token)

    st.markdown("### История статусов")
    timeline: list[dict[str, object]] = []
    try:
        timeline_result = client.get_json(
            f"/applications/{selected_application_id}/timeline",
            token=token,
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code} при загрузке timeline")
        st.code(exc.response.text)
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend для загрузки timeline")
        st.code(str(exc))
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ для timeline")
        st.code(str(exc))
    else:
        if not isinstance(timeline_result, list):
            st.error("Backend вернул неожиданный формат timeline")
            st.json(timeline_result)
        else:
            timeline = timeline_result

    if timeline:
        for item in timeline:
            previous_status = item.get("previous_status") or "—"
            new_status = item.get("new_status") or "—"
            changed_at = format_optional_datetime(item.get("changed_at"))

            with st.container(border=True):
                st.markdown(f"**{changed_at}**")
                st.write(f"{previous_status} -> {new_status}")
                if item.get("notes"):
                    st.caption(item.get("notes"))
    else:
        st.caption("История статусов пока пуста.")

    st.markdown("### Журнал действий")
    activity_log: list[dict[str, object]] = []
    try:
        activity_log_result = client.get_json(
            f"/applications/{selected_application_id}/activity-log",
            token=token,
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code} при загрузке журнала действий")
        st.code(exc.response.text)
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend для загрузки журнала действий")
        st.code(str(exc))
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ для журнала действий")
        st.code(str(exc))
    else:
        if not isinstance(activity_log_result, list):
            st.error("Backend вернул неожиданный формат журнала действий")
            st.json(activity_log_result)
        else:
            activity_log = activity_log_result

    def _render_activity_meta(meta_json: dict[str, object] | None) -> None:
        if not meta_json:
            st.caption("мета: —")
            return

        important_keys = [
            "vacancy_id",
            "resume_document_id",
            "cover_letter_document_id",
            "previous_status",
            "new_status",
            "source",
            "external_link",
            "applied_at",
        ]
        important_parts = []
        for key in important_keys:
            value = meta_json.get(key)
            if value not in (None, "", []):
                important_parts.append(f"{key}={value}")

        if important_parts:
            st.caption("мета: " + ", ".join(important_parts))
        else:
            st.caption("мета: " + ", ".join(f"{key}={value}" for key, value in meta_json.items()))

    if activity_log:
        for item in activity_log:
            with st.container(border=True):
                st.markdown(f"**{item.get('title') or item.get('event_type') or 'Событие'}**")
                st.caption(format_optional_datetime(item.get("created_at")))
                if item.get("description"):
                    st.write(item.get("description"))
                _render_activity_meta(item.get("meta_json") or {})
    else:
        st.caption("Журнал действий пока пуст.")

    current_status = str(selected_application.get("status") or "").strip().lower()

    try:
        workflow = client.get_json(f"/applications/{selected_application_id}/workflow", token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ")
        st.code(str(exc))
        return

    if not isinstance(workflow, dict):
        st.error("Backend вернул неожиданный формат workflow metadata")
        st.json(workflow)
        return

    allowed_transitions = workflow.get("allowed_transitions") or []
    next_statuses = [
        str(item.get("status") or "").strip()
        for item in allowed_transitions
        if isinstance(item, dict) and str(item.get("status") or "").strip()
    ]
    transition_labels = {
        str(item.get("status") or "").strip(): str(item.get("label") or "").strip()
        for item in allowed_transitions
        if isinstance(item, dict) and str(item.get("status") or "").strip()
    }

    st.markdown("### Ручное обновление статуса")

    if not next_statuses:
        st.info(
            "Для текущего статуса нет разрешённых следующих переходов. "
            "Финальные статусы не переоткрываются автоматически."
        )
        with st.expander("Метаданные workflow", expanded=False):
            st.json(workflow)
        return

    with st.form(f"application_status_dashboard_form_{selected_application_id}"):
        next_status = st.selectbox(
            "Новый статус",
            options=next_statuses,
            format_func=lambda value: transition_labels.get(value, status_labels.get(value, value)),
        )

        notes = st.text_area(
            "Заметка к изменению статуса",
            value="Статус обновлён вручную через Streamlit dashboard.",
            height=90,
        )

        submitted = st.form_submit_button(
            "Сохранить новый статус",
            type="primary",
            width="stretch",
        )

    if submitted:
        try:
            updated_application = client.patch_json(f"/applications/{selected_application_id}/status",
                {
                    "status": next_status,
                    "notes": notes.strip() or None,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Не удалось подключиться к backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend вернул неожиданный ответ")
            st.code(str(exc))
            return

        if not isinstance(updated_application, dict):
            st.error("Backend вернул неожиданный формат отклика")
            st.json(updated_application)
            return

        st.success("Статус отклика обновлён")
        st.rerun()


def render_mvp_flow(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("MVP-сценарий")

    if not token:
        st.warning("Войдите или зарегистрируйтесь, чтобы пройти MVP-сценарий.")
        return

    render_resume_upload_step(client, token=token)

    st.divider()

    render_resume_import_step(client, token=token)

    st.divider()

    render_structured_profile_step(client, token=token)

    st.divider()

    render_achievements_step(client, token=token)

    st.divider()

    render_vacancy_import_step(client, token=token)

    st.divider()

    render_vacancy_analysis_step(client, token=token)

    st.divider()

    render_resume_generation_step(client, token=token)

    st.divider()

    render_cover_letter_generation_step(client, token=token)

    st.divider()

    render_document_approval_step(client, token=token)

    st.divider()

    render_application_creation_step(client, token=token)

    st.divider()

    render_application_status_update_step(client, token=token)

    st.divider()

    st.info(
        "После создания и ручной отправки отклика используйте вкладку «Отклики» "
        "для дальнейшего workflow, analytics и tracking."
    )

    st.divider()

    render_interview_preparation_step(client, token=token)

    st.divider()

    st.success(
        "Сквозной MVP-сценарий во frontend подключён: резюме → вакансия → документы → "
        "ручной отклик → подготовка к интервью."
    )


def main() -> None:
    init_session_state()
    _, client, token = render_sidebar()

    tab_home, tab_health, tab_flow, tab_review, tab_prep, tab_trust, tab_evidence, tab_strategy, tab_applications = st.tabs(
        [
            "Главная",
            "Состояние системы",
            "MVP-сценарий",
            "Проверка документов",
            "Подготовка к интервью",
            "Панель доверия",
            "Источники доказательств",
            "Стратегия карьеры",
            "Отклики",
        ]
    )

    with tab_home:
        render_home()

    with tab_health:
        _render_system_health(client, token=token)

    with tab_flow:
        render_mvp_flow(client, token=token)

    with tab_review:
        render_document_review_workspace_tab(
            client,
            token=token,
            selection_state_key="document_review_workspace_tab_selection",
        )

    with tab_prep:
        render_interview_prep_workspace_tab(
            client,
            token=token,
            selection_state_key="interview_prep_workspace_selection",
        )

    with tab_trust:
        _render_trust_panel(client, token=token)

    with tab_evidence:
        render_evidence_workspace_tab(client, token=token)

    with tab_strategy:
        render_career_strategy_workspace_tab(client, token=token)

    with tab_applications:
        render_application_dashboard(client, token=token)


if __name__ == "__main__":
    main()
