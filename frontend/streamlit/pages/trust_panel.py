# frontend\streamlit\pages\trust_panel.py

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient
from ui.formatting import (
    _action_badge_tone,
    _confidence_badge_tone,
    _format_confidence_value,
    _format_label,
    _humanize_document_kind_for_trust_panel,
    _render_inline_badges,
    _render_trust_panel_list,
    _risk_badge_tone,
    _translate_trust_text,
)
from ui.labels import (
    ACTION_GROUP_ORDER,
    ACTION_SEVERITY_LABELS,
    ENTITY_TYPE_LABELS,
    RISK_LEVEL_LABELS,
)


def _source_label(source_type: Any) -> str:
    source = str(source_type or "").strip().lower()
    return {
        "resume": "Резюме",
        "resume_structured": "Структурированное резюме",
        "github_repository_analysis": "GitHub-проекты",
        "github": "GitHub-проекты",
        "manual": "Ручное подтверждение",
        "application": "Отклики",
        "interview": "Подготовка к интервью",
    }.get(source, str(source_type or "—"))


def _fact_status_label(fact_status: Any) -> str:
    status = str(fact_status or "").strip().lower()
    return {
        "confirmed": "Подтверждено",
        "user_provided": "Есть в профиле",
        "needs_confirmation": "Требует подтверждения",
        "partial": "Подтверждено частично",
        "rejected": "Отклонено",
        "unverified": "Требует проверки",
    }.get(status, str(fact_status or "—"))


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
            with st.expander("Технические детали", expanded=False):
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


def render_trust_panel(
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
                        f"{_humanize_document_kind_for_trust_panel(source_document.get('document_kind'))}"
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
        for index, item in enumerate(sessions, start=1):
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("id") or "").strip()
            if not session_id:
                continue
            status_label = _translate_trust_text(str(item.get("prep_status") or "draft"))
            candidates.append(
                {
                    "id": session_id,
                    "label": f"Сессия подготовки {index} · {status_label}",
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

    if not client.has_entity_id(entity_id):
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
        st.error("Панель доверия временно недоступна.")
        with st.expander("Технические детали", expanded=False):
            st.caption(f"HTTP {exc.response.status_code}")
            st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ.")
        with st.expander("Технические детали", expanded=False):
            st.code(str(exc))
        return

    if not isinstance(summary, dict):
        st.error("Backend вернул неожиданный формат summary.")
        with st.expander("Технические детали", expanded=False):
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
        f"{ENTITY_TYPE_LABELS.get(entity_type, entity_type)} · "
        f"требуется ручная проверка={summary.get('requires_human_review', True)}"
    )
    with st.expander("Технические детали", expanded=False):
        st.caption(f"entity_id: {entity_id}")

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
                    "Заголовок": item.get("title") or "—",
                    "Источник": _source_label(item.get("source_type")),
                    "Статус факта": _fact_status_label(item.get("fact_status")),
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



