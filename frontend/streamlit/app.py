# frontend\streamlit\app.py

from __future__ import annotations

import streamlit as st

from components import (
    render_career_strategy_workspace_tab,
    render_document_review_workspace_tab,
    render_evidence_workspace_tab,
    render_interview_prep_workspace_tab,
)
from flows.mvp_flow import render_mvp_flow
from pages.applications import render_application_dashboard
from pages.home import render_home
from pages.system_health import render_system_health
from pages.trust_panel import render_trust_panel
from ui.navigation import apply_pending_navigation
from ui.auth import render_sidebar
from ui.state import init_session_state


st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧭",
    layout="wide",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _get_recommended_navigation_page() -> tuple[str, str]:
    if not st.session_state.get("resume_import"):
        return "MVP-сценарий", "начать с резюме"

    if not st.session_state.get("vacancy_analysis"):
        return "MVP-сценарий", "добавить и разобрать вакансию"

    if not (
        st.session_state.get("approved_resume")
        and st.session_state.get("approved_cover_letter")
    ):
        return "Проверка документов", "проверить документы"

    if not st.session_state.get("application"):
        return "MVP-сценарий", "сохранить отклик"

    application = st.session_state.get("application") or {}
    status = str(application.get("status") or "").strip().lower()
    if status not in {"applied", "manual_applied", "sent_manually", "отправлен вручную"}:
        return "Отклики", "обновить статус отклика"

    return "Подготовка к интервью", "подготовиться к интервью"


def main() -> None:
    init_session_state()
    apply_pending_navigation()

    pages = {
        "Главная": render_home,
        "MVP-сценарий": "mvp_flow",
        "Проверка документов": "document_review",
        "Подготовка к интервью": "interview_prep",
        "Отклики": "applications",
        "Стратегия карьеры": "career_strategy",
        "Источники доказательств": "evidence",
        "Панель доверия": "trust_panel",
        "Диагностика": "system_health",
    }

    recommended_page, recommended_reason = _get_recommended_navigation_page()

    st.sidebar.markdown("## Навигация")
    selected_page = st.sidebar.radio(
        "Раздел",
        options=list(pages.keys()),
        key="main_navigation_page",
        format_func=lambda page: f"⭐ {page}" if page == recommended_page else page,
    )
    st.sidebar.caption(f"⭐ Рекомендуется сейчас: {recommended_reason}.")

    if selected_page == "Главная":
        st.sidebar.info("Начните с кнопки «Продолжить MVP-сценарий» на главной.")
    elif selected_page == "MVP-сценарий":
        st.sidebar.info("Проходите шаги сверху вниз. Текущий шаг раскрыт автоматически.")
    elif selected_page == "Проверка документов":
        st.sidebar.info("Здесь можно проверить, скачать и утвердить резюме или письмо.")
    elif selected_page == "Подготовка к интервью":
        st.sidebar.info("Здесь создаются вопросы и черновики ответов по выбранной вакансии.")
    elif selected_page == "Отклики":
        st.sidebar.info("Здесь отслеживаются сохранённые отклики и статусы.")
    elif selected_page == "Диагностика":
        st.sidebar.warning("Технический раздел для проверки backend и демо-данных.")

    if selected_page != "Главная":
        st.sidebar.markdown("---")
        st.sidebar.caption("Главная страница показывает следующий рекомендуемый шаг.")

    st.sidebar.markdown("---")
    _, client, token = render_sidebar()

    if selected_page == "Главная":
        render_home()
    elif selected_page == "Диагностика":
        render_system_health(client, token=token)
    elif selected_page == "MVP-сценарий":
        render_mvp_flow(client, token=token)
    elif selected_page == "Проверка документов":
        render_document_review_workspace_tab(
            client,
            token=token,
            selection_state_key="document_review_workspace_tab_selection",
        )
    elif selected_page == "Подготовка к интервью":
        render_interview_prep_workspace_tab(
            client,
            token=token,
            selection_state_key="interview_prep_workspace_selection",
        )
    elif selected_page == "Панель доверия":
        render_trust_panel(client, token=token)
    elif selected_page == "Источники доказательств":
        render_evidence_workspace_tab(client, token=token)
    elif selected_page == "Стратегия карьеры":
        render_career_strategy_workspace_tab(client, token=token)
    elif selected_page == "Отклики":
        render_application_dashboard(client, token=token)


if __name__ == "__main__":
    main()
