# frontend\streamlit\flows\mvp_flow.py

from __future__ import annotations

import streamlit as st

from api_client import CareerCopilotApiClient
from flows.document_application_flow import (
    render_application_creation_step,
    render_application_status_update_step,
    render_application_tracking_step,
    render_cover_letter_generation_step,
    render_document_approval_step,
    render_interview_preparation_step,
    render_resume_generation_step,
)
from flows.resume_intake import (
    render_achievements_step,
    render_resume_import_step,
    render_resume_upload_step,
    render_structured_profile_step,
)
from flows.vacancy_flow import (
    render_vacancy_analysis_step,
    render_vacancy_import_step,
)


def _status_label(done: bool, warning: bool, label: str) -> str:
    if done:
        return f"✓ {label}"
    if warning:
        return f"⚠ {label}"
    return f"□ {label}"


def _render_workflow_status_strip() -> None:
    application = st.session_state.get("application") or {}
    app_status = str(application.get("status") or "").strip().lower()
    achievements = st.session_state.get("achievements") or []
    confirmed_count = sum(
        1
        for item in achievements
        if isinstance(item, dict)
        and str(item.get("fact_status") or "").strip().lower() == "confirmed"
    )
    needs_confirmation_count = sum(
        1
        for item in achievements
        if isinstance(item, dict)
        and str(item.get("fact_status") or "").strip().lower()
        in {"needs_confirmation", "partial", "unverified"}
    )

    statuses = [
        _status_label(bool(st.session_state.get("resume_import")), False, "Резюме загружено"),
        _status_label(bool(st.session_state.get("github_import_notice")), False, "GitHub импортирован"),
        _status_label(confirmed_count > 0, needs_confirmation_count > 0, "Факты подтверждены"),
        _status_label(bool(st.session_state.get("vacancy_analysis")), False, "Вакансия проанализирована"),
        _status_label(bool(st.session_state.get("generated_resume")), False, "Резюме сгенерировано"),
        _status_label(
            bool(st.session_state.get("approved_cover_letter")),
            bool(st.session_state.get("generated_cover_letter")),
            "Письмо подготовлено",
        ),
        _status_label(app_status == "applied", app_status in {"draft", "ready"}, "Отклик отправлен"),
        _status_label(
            bool(st.session_state.get("interview_prep_workspace_flow_selection")),
            False,
            "Подготовка к интервью",
        ),
    ]

    st.markdown("### Статус сценария")
    cols = st.columns(4)
    for index, status in enumerate(statuses):
        with cols[index % 4]:
            if status.startswith("✓"):
                st.success(status)
            elif status.startswith("⚠"):
                st.warning(status)
            else:
                st.info(status)


def render_mvp_flow(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("MVP-сценарий")

    if not token:
        st.warning("Войдите или зарегистрируйтесь, чтобы пройти MVP-сценарий.")
        return

    _render_workflow_status_strip()
    st.divider()

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

    render_application_tracking_step(client, token=token)

    st.divider()

    render_interview_preparation_step(client, token=token)

    st.divider()

    st.success(
        "Сквозной MVP-сценарий во frontend подключён: резюме → вакансия → документы → "
        "ручной отклик → подготовка к интервью."
    )
