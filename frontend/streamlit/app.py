# frontend\streamlit\app.py

from __future__ import annotations

import os

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient, DEFAULT_API_BASE_URL


st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧭",
    layout="wide",
)


def init_session_state() -> None:
    if "source_file" not in st.session_state:
        st.session_state.source_file = None
    if "resume_import" not in st.session_state:
        st.session_state.resume_import = None
    if "structured_profile" not in st.session_state:
        st.session_state.structured_profile = None


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


def render_resume_upload_step(client: CareerCopilotApiClient) -> None:
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

    if st.button("Загрузить резюме", type="primary", use_container_width=True):
        try:
            result = client.upload_file(
                path="/files/upload",
                file_kind="resume",
                filename=uploaded_file.name,
                content=uploaded_file.getvalue(),
                content_type=uploaded_file.type or "application/octet-stream",
            )
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


def render_resume_import_step(client: CareerCopilotApiClient) -> None:
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

    if st.button("Импортировать резюме", type="primary", use_container_width=True):
        try:
            result = client.post_json(
                "/profile/import-resume",
                {
                    "source_file_id": source_file_id,
                },
            )
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


def render_structured_profile_step(client: CareerCopilotApiClient) -> None:
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

    if st.button("Извлечь структурированный профиль", type="primary", use_container_width=True):
        try:
            result = client.post_json(
                "/profile/extract-structured",
                {
                    "extraction_id": extraction_id,
                },
            )
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
        st.success("Структурированный профиль извлечён")

    if st.session_state.structured_profile:
        profile = st.session_state.structured_profile

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
                st.warning(warning)

        with st.expander("Raw JSON результата", expanded=False):
            st.json(profile)


def render_mvp_flow(client: CareerCopilotApiClient) -> None:
    st.header("MVP-сценарий")

    render_resume_upload_step(client)

    st.divider()

    render_resume_import_step(client)

    st.divider()

    render_structured_profile_step(client)

    st.divider()

    steps = [
        "4. Извлечь достижения",
        "5. Импортировать вакансию",
        "6. Проанализировать вакансию",
        "7. Сгенерировать адаптированное резюме",
        "8. Сгенерировать сопроводительное письмо",
        "9. Подтвердить документы",
        "10. Создать отклик",
        "11. Создать подготовку к интервью",
    ]

    st.subheader("Следующие шаги")
    for step in steps:
        st.checkbox(step, value=False, disabled=True)

    st.warning("Следующие действия будут подключаться по одному в Priority 10.5+.")


def main() -> None:
    init_session_state()
    _, client = render_sidebar()

    tab_home, tab_flow = st.tabs(["Главная", "MVP-сценарий"])

    with tab_home:
        render_home()

    with tab_flow:
        render_mvp_flow(client)


if __name__ == "__main__":
    main()
