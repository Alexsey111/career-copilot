# frontend\streamlit\pages\home.py

from __future__ import annotations

import streamlit as st

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


