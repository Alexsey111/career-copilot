# frontend\streamlit\pages\home.py

from __future__ import annotations

import streamlit as st

from ui.navigation import navigate_to_page

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


def _is_ready(value: object) -> bool:
    return bool(value)


def _status_chip(label: str, ready: bool) -> str:
    return f"✅ {label}" if ready else f"□ {label}"


def _status_card(label: str, ready: bool) -> None:
    if ready:
        st.success(f"✅ {label}")
    else:
        st.info(f"□ {label}")


def _get_resume_summary() -> dict:
    profile = st.session_state.get("structured_profile") or {}
    achievements = st.session_state.get("achievements") or {}
    return {
        "name": profile.get("full_name") or "—",
        "headline": profile.get("headline") or "—",
        "experience_count": profile.get("experience_count", 0),
        "achievement_count": achievements.get("achievement_count", 0),
    }


def _get_vacancy_summary() -> dict:
    vacancy = st.session_state.get("vacancy") or {}
    analysis = st.session_state.get("vacancy_analysis") or {}
    return {
        "title": vacancy.get("title") or "—",
        "company": vacancy.get("company") or "—",
        "match_score": analysis.get("match_score"),
        "is_analyzed": bool(analysis),
    }


def _get_documents_summary() -> dict:
    resume = st.session_state.get("approved_resume") or st.session_state.get("generated_resume") or {}
    letter = (
        st.session_state.get("approved_cover_letter")
        or st.session_state.get("generated_cover_letter")
        or {}
    )
    return {
        "resume_status": resume.get("review_status") or (
            "выбрано" if st.session_state.get("approved_resume") else "—"
        ),
        "letter_status": letter.get("review_status") or (
            "выбрано" if st.session_state.get("approved_cover_letter") else "—"
        ),
    }


def _set_main_page(page_name: str) -> None:
    navigate_to_page(page_name)


def _render_home_status_overview() -> None:
    resume_ready = _is_ready(st.session_state.get("resume_import"))
    profile_ready = _is_ready(st.session_state.get("structured_profile"))
    vacancy_ready = _is_ready(st.session_state.get("vacancy_analysis"))
    documents_ready = bool(
        st.session_state.get("approved_resume")
        and st.session_state.get("approved_cover_letter")
    )
    application_ready = _is_ready(st.session_state.get("application"))

    st.markdown("### Где вы сейчас")

    col_resume, col_profile, col_vacancy, col_docs, col_application = st.columns(5)

    with col_resume:
        _status_card("Резюме", resume_ready)
    with col_profile:
        _status_card("Профиль", profile_ready)
    with col_vacancy:
        _status_card("Вакансия", vacancy_ready)
    with col_docs:
        _status_card("Документы", documents_ready)
    with col_application:
        _status_card("Отклик", application_ready)


def _render_home_context_cards() -> None:
    st.markdown("### Текущий контекст")

    resume = _get_resume_summary()
    vacancy = _get_vacancy_summary()
    documents = _get_documents_summary()

    col_profile, col_vacancy, col_documents = st.columns(3)

    with col_profile:
        with st.container(border=True):
            st.markdown("#### Профиль")
            st.caption(f"Имя: {resume['name']}")
            st.caption(f"Позиционирование: {resume['headline']}")
            st.metric("Опытов работы", resume["experience_count"])
            st.metric("Достижений", resume["achievement_count"])

    with col_vacancy:
        with st.container(border=True):
            st.markdown("#### Вакансия")
            st.caption(f"Название: {vacancy['title']}")
            st.caption(f"Компания: {vacancy['company']}")
            if vacancy["match_score"] is not None:
                st.metric("Совпадение", vacancy["match_score"])
            else:
                st.caption("Анализ пока не выполнен.")

    with col_documents:
        with st.container(border=True):
            st.markdown("#### Документы")
            st.caption(f"Резюме: {documents['resume_status']}")
            st.caption(f"Письмо: {documents['letter_status']}")


def _render_home_quick_actions() -> None:
    st.markdown("### Быстрые действия")

    col_main, col_docs, col_interview, col_apps = st.columns(4)

    with col_main:
        if st.button("Продолжить MVP-сценарий", type="primary", width="stretch"):
            _set_main_page("MVP-сценарий")

    with col_docs:
        if st.button("Проверить документы", width="stretch"):
            _set_main_page("Проверка документов")

    with col_interview:
        if st.button("Подготовиться к интервью", width="stretch"):
            _set_main_page("Подготовка к интервью")

    with col_apps:
        if st.button("Открыть отклики", width="stretch"):
            _set_main_page("Отклики")


def _get_recommended_next_page() -> tuple[str, str, str]:
    if not st.session_state.get("resume_import"):
        return (
            "MVP-сценарий",
            "Начать с резюме",
            "Загрузите или переиспользуйте резюме, чтобы собрать профиль кандидата.",
        )

    if not st.session_state.get("vacancy_analysis"):
        return (
            "MVP-сценарий",
            "Добавить и разобрать вакансию",
            "Импортируйте вакансию и получите разбор требований.",
        )

    if not (
        st.session_state.get("approved_resume")
        and st.session_state.get("approved_cover_letter")
    ):
        return (
            "Проверка документов",
            "Проверить документы",
            "Утвердите резюме и сопроводительное письмо перед откликом.",
        )

    if not st.session_state.get("application"):
        return (
            "MVP-сценарий",
            "Сохранить отклик",
            "Создайте внутреннюю запись отклика и сохраните пакет документов.",
        )

    application = st.session_state.get("application") or {}
    status = str(application.get("status") or "").strip().lower()
    if status not in {"applied", "manual_applied", "sent_manually", "отправлен вручную"}:
        return (
            "Отклики",
            "Обновить статус отклика",
            "Отметьте, что отклик отправлен вручную, или обновите его статус.",
        )

    return (
        "Подготовка к интервью",
        "Подготовиться к интервью",
        "Сгенерируйте вопросы и черновики ответов под выбранную вакансию.",
    )


def _render_recommended_next_step() -> None:
    page_name, title, description = _get_recommended_next_page()

    st.markdown("### Следующий рекомендуемый шаг")

    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(description)

        if st.button(f"Перейти: {title}", type="primary", width="stretch"):
            _set_main_page(page_name)



def render_home() -> None:
    st.title("AI Career Copilot")
    st.caption("Помощник кандидата: резюме → вакансия → документы → отклик → интервью.")

    st.info(
        "Сервис помогает подготовить качественный отклик, но не отправляет его автоматически. "
        "Все документы и действия подтверждает пользователь."
    )

    _render_home_status_overview()
    st.divider()
    _render_home_context_cards()
    st.divider()
    _render_recommended_next_step()
    st.divider()
    _render_home_quick_actions()

    st.divider()
    with st.expander("Что умеет MVP", expanded=False):
        st.markdown(
            """
- загрузить или переиспользовать резюме;
- извлечь профиль и достижения;
- импортировать вакансию;
- разобрать требования вакансии;
- сгенерировать адаптированное резюме;
- подготовить сопроводительное письмо;
- проверить и утвердить документы;
- сохранить отклик в трекере;
- подготовиться к интервью по вакансии.
"""
        )
