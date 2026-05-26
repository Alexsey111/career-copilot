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
from ui.auth import render_sidebar
from ui.state import init_session_state


st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧭",
    layout="wide",
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
        render_system_health(client, token=token)

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
        render_trust_panel(client, token=token)

    with tab_evidence:
        render_evidence_workspace_tab(client, token=token)

    with tab_strategy:
        render_career_strategy_workspace_tab(client, token=token)

    with tab_applications:
        render_application_dashboard(client, token=token)


if __name__ == "__main__":
    main()
