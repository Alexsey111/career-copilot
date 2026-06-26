# frontend\streamlit\flows\mvp_flow.py

from __future__ import annotations

import streamlit as st

from api_client import CareerCopilotApiClient
from flows.document_application_flow import (
    render_application_creation_step,
    render_application_status_update_step,
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
from ui.navigation import get_forced_mvp_step


def _status_label(done: bool, warning: bool, label: str) -> str:
    if done:
        return f"✓ {label}"
    if warning:
        return f"⚠ {label}"
    return f"□ {label}"


def _determine_current_mvp_step() -> int:
    if not st.session_state.get("source_file"):
        return 1
    if not st.session_state.get("resume_import"):
        return 2
    if not st.session_state.get("structured_profile"):
        return 3
    if not st.session_state.get("achievements"):
        return 4
    if not st.session_state.get("vacancy"):
        return 5
    if not st.session_state.get("vacancy_analysis"):
        return 6
    if not st.session_state.get("generated_resume"):
        return 7
    if not st.session_state.get("generated_cover_letter"):
        return 8
    if not (
        st.session_state.get("approved_resume")
        and st.session_state.get("approved_cover_letter")
    ):
        return 9
    if not st.session_state.get("application"):
        return 10

    application = st.session_state.get("application") or {}
    status = str(application.get("status") or "").strip().lower()
    if status not in {"applied", "manual_applied", "sent_manually", "отправлен вручную"}:
        return 11

    return 12


def _render_mvp_progress_header(current_step: int) -> None:
    total_steps = 12
    progress = min(max(current_step / total_steps, 0.0), 1.0)

    st.markdown("### Прогресс MVP-сценария")
    st.progress(progress)
    st.caption(f"Текущий шаг: {current_step} из {total_steps}")

    step_labels = {
        1: "Источник резюме / профиля",
        2: "Импорт резюме",
        3: "Структурированный профиль",
        4: "Достижения",
        5: "Импорт вакансии",
        6: "Анализ вакансии",
        7: "Адаптированное резюме",
        8: "Сопроводительное письмо",
        9: "Проверка документов",
        10: "Отклик в трекере",
        11: "Отправка и отслеживание",
        12: "Подготовка к интервью",
    }

    st.info(f"Сейчас нужно: {step_labels.get(current_step, 'продолжить сценарий')}")


def _step_status_prefix(step_number: int, current_step: int) -> str:
    if step_number < current_step:
        return "✓"
    if step_number == current_step:
        return "▶"
    return "□"


def _mvp_step_hint(step_number: int) -> str:
    return {
        1: "Выберите источник данных: загрузите готовое резюме или начните заполнение профиля.",
        2: "Система извлечёт текст и подготовит его для дальнейшего анализа.",
        3: "Проверьте, что профиль распознан корректно: опыт, навыки и контакты.",
        4: "Подтвердите достижения, которые можно безопасно использовать в документах.",
        5: "Добавьте вакансию, под которую будут адаптированы документы.",
        6: "Изучите требования вакансии и убедитесь, что анализ соответствует ожиданиям.",
        7: "Сгенерируйте адаптированное резюме на основе подтверждённых данных.",
        8: "Сформируйте сопроводительное письмо без выдуманных фактов.",
        9: "Проверьте документы и подтвердите версии, которые готовы к использованию.",
        10: "Создайте запись отклика для отслеживания процесса трудоустройства.",
        11: "Отметьте текущий статус отклика после действий вне системы.",
        12: "Подготовьтесь к интервью по требованиям выбранной вакансии.",
    }.get(step_number, "")


def _render_mvp_step(
    *,
    step_number: int,
    current_step: int,
    title: str,
    render_fn,
    client: CareerCopilotApiClient,
    token: str | None,
) -> None:
    prefix = _step_status_prefix(step_number, current_step)
    expanded = step_number == current_step

    with st.expander(
        f"{prefix} {step_number}. {title}",
        expanded=expanded,
    ):
        hint = _mvp_step_hint(step_number)
        if hint:
            st.caption(hint)

        st.divider()

        render_fn(
            client,
            token=token,
            show_title=False,
        )


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

    with st.expander("Подробный статус сценария", expanded=False):
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

    current_step = get_forced_mvp_step() or _determine_current_mvp_step()

    _render_mvp_progress_header(current_step)
    st.divider()
    _render_workflow_status_strip()
    st.divider()

    steps = [
        (1, "Источник резюме / профиля", render_resume_upload_step),
        (2, "Импорт резюме", render_resume_import_step),
        (3, "Структурированный профиль", render_structured_profile_step),
        (4, "Достижения", render_achievements_step),
        (5, "Импорт вакансии", render_vacancy_import_step),
        (6, "Анализ вакансии", render_vacancy_analysis_step),
        (7, "Адаптированное резюме", render_resume_generation_step),
        (8, "Сопроводительное письмо", render_cover_letter_generation_step),
        (9, "Проверка документов", render_document_approval_step),
        (10, "Отклик в трекере", render_application_creation_step),
        (11, "Отправка и отслеживание", render_application_status_update_step),
        (12, "Подготовка к интервью", render_interview_preparation_step),
    ]

    for step_number, title, render_fn in steps:
        _render_mvp_step(
            step_number=step_number,
            current_step=current_step,
            title=title,
            render_fn=render_fn,
            client=client,
            token=token,
        )

    st.divider()

    if current_step >= 12:
        st.success(
            "Сквозной MVP-сценарий пройден: резюме → вакансия → документы → "
            "ручной отклик → подготовка к интервью."
        )
    else:
        st.caption(
            "Сценарий ведёт пользователя по цепочке: резюме → вакансия → документы → "
            "ручной отклик → подготовка к интервью."
        )
