# frontend\streamlit\app.py

from __future__ import annotations

import os

import streamlit as st

from api_client import CareerCopilotApiClient, DEFAULT_API_BASE_URL


st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧭",
    layout="wide",
)


def render_sidebar() -> tuple[str, CareerCopilotApiClient]:
    st.sidebar.header("Backend")

    default_api_base_url = os.getenv(
        "CAREER_COPILOT_API_BASE_URL",
        DEFAULT_API_BASE_URL,
    )

    api_base_url = st.sidebar.text_input(
        "Базовый URL API",
        value=default_api_base_url,
        help="Например: http://localhost:8000/api/v1",
    ).strip()

    client = CareerCopilotApiClient(api_base_url=api_base_url)

    if st.sidebar.button("Проверить соединение с backend", use_container_width=True):
        result = client.check_backend()

        if result.ok:
            st.sidebar.success("Backend доступен")
            st.sidebar.caption(f"Название API: {result.app_title}")
            st.sidebar.caption(f"OpenAPI routes: {result.path_count}")
        else:
            st.sidebar.error("Не удалось подключиться к backend")
            st.sidebar.caption(result.error)

    return api_base_url, client


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
- сохранение ответов на вопросы интервью и базовая обратная связь.
"""
    )

    st.info(
        "Priority 10.1 добавляет только каркас frontend и API-клиент. "
        "Полный MVP-сценарий будет подключаться по шагам."
    )


def render_flow_placeholder() -> None:
    st.header("MVP-сценарий")

    steps = [
        "1. Загрузить резюме",
        "2. Импортировать резюме",
        "3. Извлечь структурированный профиль",
        "4. Извлечь достижения",
        "5. Импортировать вакансию",
        "6. Проанализировать вакансию",
        "7. Сгенерировать адаптированное резюме",
        "8. Сгенерировать сопроводительное письмо",
        "9. Подтвердить документы",
        "10. Создать отклик",
        "11. Создать подготовку к интервью",
    ]

    for step in steps:
        st.checkbox(step, value=False, disabled=True)

    st.warning("Управление сценарием будет добавлено в Priority 10.2+.")


def main() -> None:
    _, _client = render_sidebar()

    tab_home, tab_flow = st.tabs(["Главная", "MVP-сценарий"])

    with tab_home:
        render_home()

    with tab_flow:
        render_flow_placeholder()


if __name__ == "__main__":
    main()