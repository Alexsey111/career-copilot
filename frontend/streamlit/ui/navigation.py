# frontend\streamlit\ui\navigation.py

from __future__ import annotations

import streamlit as st


MAIN_NAVIGATION_KEY = "main_navigation_page"
PENDING_NAVIGATION_KEY = "pending_navigation_page"
MVP_FORCE_STEP_KEY = "mvp_force_open_step"


def apply_pending_navigation() -> None:
    pending_page = st.session_state.pop(PENDING_NAVIGATION_KEY, None)
    if pending_page:
        st.session_state[MAIN_NAVIGATION_KEY] = pending_page


def navigate_to_page(page_name: str) -> None:
    st.session_state[MAIN_NAVIGATION_KEY] = page_name
    st.session_state[PENDING_NAVIGATION_KEY] = page_name
    st.rerun()


def navigate_to_mvp_step(step_number: int) -> None:
    st.session_state[MVP_FORCE_STEP_KEY] = int(step_number)
    navigate_to_page("MVP-сценарий")


def get_forced_mvp_step() -> int | None:
    value = st.session_state.pop(MVP_FORCE_STEP_KEY, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None