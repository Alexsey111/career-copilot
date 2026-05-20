# frontend\streamlit\app.py

from __future__ import annotations

import os

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient, DEFAULT_API_BASE_URL
from components import (
    render_career_strategy_workspace_tab,
    render_document_review_workspace_tab,
    render_evidence_workspace_tab,
    render_interview_prep_workspace_tab,
)


st.set_page_config(
    page_title="AI Career Copilot",
    page_icon="🧭",
    layout="wide",
)


APPLICATION_STATUS_LABELS = {
    "draft": "Черновик",
    "ready": "Готов к отправке",
    "applied": "Отправлен вручную",
    "screening": "Скрининг",
    "interview": "Интервью",
    "rejected": "Отказ",
    "offer": "Оффер",
    "withdrawn": "Отозван",
}

APPLICATION_OUTCOME_LABELS = {
    "rejected": "Отказ",
    "offer": "Оффер",
}

APPLICATION_REMINDER_LABELS = {
    "draft_stale": "Черновик без активности",
    "ready_not_submitted": "Готов к отправке, но не отправлен",
    "follow_up_missing": "Нет follow-up по отклику",
}

DEMO_VACANCY_TITLE_LABELS = {
    "Backend Developer": "Backend-разработчик",
}

DEMO_COMPANY_LABELS = {
    "Test Company": "Тестовая компания",
}

DEMO_LOCATION_LABELS = {
    "Remote": "Удалённо",
}


def format_application_status(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_STATUS_LABELS.get(value, value)


def format_optional_datetime(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ")[:19]


def format_application_outcome(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_OUTCOME_LABELS.get(value, value)


def format_vacancy_title(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_VACANCY_TITLE_LABELS.get(value, value)


def format_vacancy_company(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_COMPANY_LABELS.get(value, value)


def format_vacancy_location(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_LOCATION_LABELS.get(value, value)



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



def init_session_state() -> None:
    if "source_file" not in st.session_state:
        st.session_state.source_file = None
    if "resume_import" not in st.session_state:
        st.session_state.resume_import = None
    if "structured_profile" not in st.session_state:
        st.session_state.structured_profile = None
    if "achievements" not in st.session_state:
        st.session_state.achievements = None
    if "vacancy" not in st.session_state:
        st.session_state.vacancy = None
    if "vacancy_analysis" not in st.session_state:
        st.session_state.vacancy_analysis = None
    if "generated_resume" not in st.session_state:
        st.session_state.generated_resume = None
    if "generated_cover_letter" not in st.session_state:
        st.session_state.generated_cover_letter = None
    if "approved_resume" not in st.session_state:
        st.session_state.approved_resume = None
    if "approved_cover_letter" not in st.session_state:
        st.session_state.approved_cover_letter = None
    if "application" not in st.session_state:
        st.session_state.application = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None


def render_sidebar() -> tuple[str, CareerCopilotApiClient, str | None]:
    st.sidebar.header("Backend")

    api_base_url = st.sidebar.text_input(
        "Базовый URL API",
        value=os.getenv("CAREER_COPILOT_API_BASE_URL", DEFAULT_API_BASE_URL),
        help="Например: http://localhost:8000/api/v1",
    ).strip()

    client = CareerCopilotApiClient(api_base_url=api_base_url)
    token = st.session_state.get("auth_token")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔐 Авторизация")

    if not token:
        email = st.sidebar.text_input("Email", key="auth_email")
        password = st.sidebar.text_input("Пароль", type="password", key="auth_password")
        if st.sidebar.button("Войти", use_container_width=True, type="primary"):
            try:
                result = client.login(email.strip(), password)
                st.session_state.auth_token = result.get("access_token")
                st.session_state.user_email = email.strip()
                st.sidebar.success("✅ Авторизация успешна")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Ошибка входа: {e}")
    else:
        st.sidebar.success(f"👤 {st.session_state.get('user_email', 'user')}")
        st.sidebar.caption(f"Токен активен до завершения сессии")
        if st.sidebar.button("Выйти", use_container_width=True):
            st.session_state.pop("auth_token", None)
            st.session_state.pop("user_email", None)
            st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("Проверить соединение", use_container_width=True):
        result = client.check_backend()
        if result.ok:
            st.sidebar.success("✅ Backend доступен")
        else:
            st.sidebar.error(f"❌ {result.error}")

    return api_base_url, client, token


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
- Interview Prep Workspace;
- сохранение ответов на вопросы интервью и базовая обратная связь.
"""
    )

    st.info(
        "Frontend подключает полный MVP-сценарий. "
        "Все внешние действия остаются human-in-the-loop: система не отправляет отклики автоматически."
    )


def render_resume_upload_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
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
            result = client.upload_file(path="/files/upload",
                file_kind="resume",
                filename=uploaded_file.name,
                content=uploaded_file.getvalue(),
                content_type=uploaded_file.type or "application/octet-stream", token=token)
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
        st.session_state.achievements = None
        st.session_state.vacancy = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
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


def render_resume_import_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
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
            result = client.post_json("/profile/import-resume",
                {
                    "source_file_id": source_file_id,
                }, token=token)
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
        st.session_state.achievements = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
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


def render_structured_profile_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
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
            result = client.post_json("/profile/extract-structured",
                {
                    "extraction_id": extraction_id,
                }, token=token)
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
        st.session_state.achievements = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
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


def render_achievements_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("4. Извлечение достижений")

    resume_import = st.session_state.resume_import
    if not resume_import:
        st.info("Сначала импортируйте резюме на шаге 2.")
        return

    structured_profile = st.session_state.structured_profile
    if not structured_profile:
        st.info("Сначала извлеките структурированный профиль на шаге 3.")
        return

    extraction_id = resume_import.get("extraction_id")
    if not extraction_id:
        st.error("В результате импорта не найден extraction_id.")
        st.json(resume_import)
        return

    st.caption(f"extraction_id: {extraction_id}")

    if st.button("Извлечь достижения", type="primary", use_container_width=True):
        try:
            result = client.post_json("/profile/extract-achievements",
                {
                    "extraction_id": extraction_id,
                }, token=token)
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

        st.session_state.achievements = result
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Достижения извлечены")

    if st.session_state.achievements:
        achievements_result = st.session_state.achievements

        st.markdown("### Извлечённые достижения")

        st.metric(
            "Количество достижений",
            achievements_result.get("achievement_count", 0),
        )

        st.caption(f"profile_id: {achievements_result.get('profile_id')}")
        st.caption(f"extraction_id: {achievements_result.get('extraction_id')}")

        achievements = achievements_result.get("achievements") or []
        if achievements:
            for index, achievement in enumerate(achievements, start=1):
                with st.container(border=True):
                    st.markdown(f"**{index}. {achievement.get('title', '')}**")
                    fact_status = achievement.get("fact_status")
                    if fact_status == "needs_confirmation":
                        st.warning("Требует подтверждения пользователем")
                    elif fact_status == "confirmed":
                        st.success("Подтверждено пользователем")
                    else:
                        st.caption(f"Статус факта: {fact_status}")


        if achievements:
            st.markdown("#### Проверка достижений перед документами")

            unconfirmed_achievements = [
                item for item in achievements if item.get("fact_status") != "confirmed"
            ]

            if unconfirmed_achievements:
                st.warning(
                    "Проверьте формулировки достижений перед импортом вакансии. "
                    "Шаг 5 разблокируется только когда все достижения будут confirmed."
                )
            else:
                st.success("Все извлечённые достижения подтверждены.")

            reviewed_items: list[dict] = []

            with st.form("achievement_review_form"):
                for index, achievement in enumerate(achievements, start=1):
                    achievement_id = achievement.get("id")
                    title = achievement.get("title") or ""
                    fact_status = achievement.get("fact_status") or "needs_confirmation"
                    evidence_note = achievement.get("evidence_note") or ""

                    with st.container(border=True):
                        st.markdown(f"#### Достижение {index}")

                        if not achievement_id:
                            st.error(
                                "Backend не вернул id достижения. "
                                "Повторите извлечение достижений после обновления backend."
                            )

                        edited_title = st.text_area(
                            "Текст достижения",
                            value=title,
                            height=90,
                            key=f"achievement_title_{achievement_id or index}",
                        )

                        status_options = ["needs_confirmation", "confirmed"]
                        status_labels = {
                            "needs_confirmation": "Требует подтверждения",
                            "confirmed": "Подтверждено",
                        }
                        status_index = (
                            status_options.index(fact_status)
                            if fact_status in status_options
                            else 0
                        )

                        edited_fact_status = st.selectbox(
                            "Статус факта",
                            options=status_options,
                            index=status_index,
                            key=f"achievement_status_{achievement_id or index}",
                            format_func=lambda value: status_labels.get(value, value),
                            help=(
                                "«Подтверждено» — пользователь проверил факт, и его можно использовать в документах. "
                                "«Требует подтверждения» — факт пока нельзя использовать как сильное утверждение."
                            ),
                        )

                        edited_evidence_note = st.text_area(
                            "Заметка / источник подтверждения",
                            value=evidence_note,
                            height=80,
                            key=f"achievement_evidence_{achievement_id or index}",
                        )

                        if edited_fact_status == "confirmed":
                            st.success("Это достижение будет считаться подтверждённым.")
                        else:
                            st.warning("Это достижение останется неподтверждённым.")

                        reviewed_items.append(
                            {
                                "id": achievement_id,
                                "title": edited_title,
                                "fact_status": edited_fact_status,
                                "evidence_note": edited_evidence_note,
                            }
                        )

                submitted_review = st.form_submit_button(
                    "Сохранить проверку достижений",
                    type="primary",
                    use_container_width=True,
                )

            if submitted_review:
                invalid_items = [
                    item
                    for item in reviewed_items
                    if not item.get("id") or not str(item.get("title") or "").strip()
                ]

                if invalid_items:
                    st.error("У всех достижений должен быть id и непустой текст.")
                    return

                try:
                    updated_items: list[dict] = []

                    for item in reviewed_items:
                        result = client.patch_json(f"/profile/achievements/{item['id']}/review",
                            {
                                "title": str(item["title"]).strip(),
                                "fact_status": item["fact_status"],
                                "evidence_note": str(item.get("evidence_note") or "").strip()
                                or None,
                            }, token=token)

                        if not isinstance(result, dict):
                            st.error("Backend вернул неожиданный формат ответа")
                            st.json(result)
                            return

                        updated_items.append(result)

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

                st.session_state.achievements = {
                    **achievements_result,
                    "achievement_count": len(updated_items),
                    "achievements": updated_items,
                }
                st.session_state.vacancy_analysis = None
                st.session_state.generated_resume = None
                st.session_state.generated_cover_letter = None
                st.session_state.approved_resume = None
                st.session_state.approved_cover_letter = None
                st.session_state.application = None

                st.success("Проверка достижений сохранена")
                st.rerun()

        warnings = achievements_result.get("warnings") or []
        if warnings:
            st.markdown("#### Предупреждения")
            for warning in warnings:
                st.warning(warning)

        with st.expander("Raw JSON результата", expanded=False):
            st.json(achievements_result)


def render_vacancy_import_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("5. Импорт вакансии")

    achievements = st.session_state.achievements
    if not achievements:
        st.info("Сначала извлеките достижения на шаге 4.")
        return

    achievement_items = achievements.get("achievements") or []
    unconfirmed_achievements = [
        item for item in achievement_items if item.get("fact_status") != "confirmed"
    ]

    if unconfirmed_achievements:
        st.info(
            "Перед импортом вакансии подтвердите достижения на шаге 4. "
            "Это защищает pipeline от использования неподтверждённого опыта в документах."
        )
        return

    default_description = """Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker
"""

    with st.form("vacancy_import_form"):
        title = st.text_input(
            "Название вакансии",
            value="Backend-разработчик",
        )
        company = st.text_input(
            "Компания",
            value="Тестовая компания",
        )
        location = st.text_input(
            "Локация",
            value="Удалённо",
        )
        source_url = st.text_input(
            "Ссылка на вакансию",
            value="",
            help="Опционально. Для MVP можно оставить пустым.",
        )
        description_raw = st.text_area(
            "Текст вакансии",
            value=default_description,
            height=220,
            help="Вставьте требования и описание вакансии вручную.",
        )

        submitted = st.form_submit_button(
            "Импортировать вакансию",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not description_raw.strip() and not source_url.strip():
            st.error("Нужно указать текст вакансии или ссылку на вакансию.")
            return

        payload = {
            "source": "manual",
            "source_url": source_url.strip() or None,
            "title": title.strip() or None,
            "company": company.strip() or None,
            "location": location.strip() or None,
            "description_raw": description_raw.strip() or None,
        }

        try:
            result = client.post_json("/vacancies/import",
                payload, token=token)
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

        st.session_state.vacancy = result
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Вакансия импортирована")

    if st.session_state.vacancy:
        vacancy = st.session_state.vacancy

        st.markdown("### Импортированная вакансия")
        st.json(
            {
                "vacancy_id": vacancy.get("vacancy_id"),
                "id": vacancy.get("id"),
                "source": vacancy.get("source"),
                "source_url": vacancy.get("source_url"),
                "title": vacancy.get("title"),
                "company": vacancy.get("company"),
                "location": vacancy.get("location"),
                "description_length": vacancy.get("description_length"),
            }
        )


def render_vacancy_analysis_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("6. Анализ вакансии")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")

    if st.button("Проанализировать вакансию", type="primary", use_container_width=True):
        try:
            result = client.post_json(f"/vacancies/{vacancy_id}/analyze",
                {}, token=token)
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

        st.session_state.vacancy_analysis = result
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Вакансия проанализирована")

    if st.session_state.vacancy_analysis:
        analysis = st.session_state.vacancy_analysis

        st.markdown("### Результат анализа")

        col_left, col_right, col_center = st.columns(3)

        with col_left:
            st.metric("Match score", analysis.get("match_score"))

        with col_center:
            st.metric("Must-have", len(analysis.get("must_have") or []))

        with col_right:
            st.metric("Nice-to-have", len(analysis.get("nice_to_have") or []))

        st.caption(f"analysis_id: {analysis.get('analysis_id')}")
        st.caption(f"analysis_version: {analysis.get('analysis_version')}")

        must_have = analysis.get("must_have") or []
        nice_to_have = analysis.get("nice_to_have") or []
        strengths = analysis.get("strengths") or []
        gaps = analysis.get("gaps") or []

        col_must, col_nice = st.columns(2)

        with col_must:
            st.markdown("#### Must-have требования")
            if must_have:
                for item in must_have:
                    st.markdown(f"- {item.get('text', item)}")
            else:
                st.caption("Не найдено")

        with col_nice:
            st.markdown("#### Nice-to-have требования")
            if nice_to_have:
                for item in nice_to_have:
                    st.markdown(f"- {item.get('text', item)}")
            else:
                st.caption("Не найдено")

        col_strengths, col_gaps = st.columns(2)

        with col_strengths:
            st.markdown("#### Сильные совпадения")
            if strengths:
                for item in strengths:
                    keyword = item.get("keyword")
                    scope = item.get("scope")
                    weight = item.get("weight")
                    evidence = item.get("evidence")
                    st.success(f"{keyword} / {scope} / weight={weight}")
                    if evidence:
                        st.caption(f"evidence: {evidence}")
            else:
                st.caption("Совпадений не найдено")

        with col_gaps:
            st.markdown("#### Gap-зоны")
            if gaps:
                for item in gaps:
                    keyword = item.get("keyword")
                    scope = item.get("scope")
                    weight = item.get("weight")
                    reason = item.get("reason")
                    st.warning(f"{keyword} / {scope} / weight={weight}")
                    if reason:
                        st.caption(f"reason: {reason}")
            else:
                st.caption("Критичных gaps не найдено")

        keywords = analysis.get("keywords") or []
        if keywords:
            with st.expander("Ключевые слова", expanded=False):
                st.write(", ".join(keywords))

        with st.expander("Raw JSON результата", expanded=False):
            st.json(analysis)

    if vacancy_id:
        st.divider()
        _render_vacancy_intelligence_block(client, vacancy_id=str(vacancy_id), token=token)


def _render_vacancy_intelligence_block(
    client: CareerCopilotApiClient,
    *,
    vacancy_id: str,
    token: str | None = None,
) -> None:
    st.markdown("### Vacancy Intelligence")
    st.caption("Deterministic fit breakdown for operational guidance, not hiring probability.")

    try:
        fit = client.get_vacancy_fit(vacancy_id, token=token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 404}:
            st.info("Vacancy intelligence is available after vacancy analysis and profile extraction.")
        else:
            st.warning(f"Vacancy intelligence unavailable: HTTP {exc.response.status_code}")
            st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.warning("Unable to connect to backend for vacancy intelligence.")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.warning("Vacancy intelligence returned an unexpected response.")
        st.code(str(exc))
        return

    if not isinstance(fit, dict):
        st.warning("Vacancy intelligence returned an unexpected payload.")
        st.json(fit)
        return

    recommendation = str(fit.get("readiness_recommendation") or "—")
    gap_severity = str(fit.get("gap_severity") or "—")

    if recommendation == "Ready to apply":
        st.success(recommendation)
    elif recommendation == "Apply with caution":
        st.warning(recommendation)
    else:
        st.error(recommendation)

    col_overall, col_skills, col_evidence, col_experience, col_leadership = st.columns(5)
    with col_overall:
        st.metric("Overall fit", fit.get("overall_fit_score", 0))
    with col_skills:
        st.metric("Skills", fit.get("skills_fit", 0))
    with col_evidence:
        st.metric("Evidence", fit.get("evidence_fit", 0))
    with col_experience:
        st.metric("Experience", fit.get("experience_fit", 0))
    with col_leadership:
        st.metric("Leadership", fit.get("leadership_fit", 0))

    st.caption(f"gap_severity: {gap_severity}")
    if fit.get("analysis_version"):
        st.caption(f"analysis_version: {fit.get('analysis_version')}")

    coverage = fit.get("evidence_coverage") or {}
    required = coverage.get("required") or []
    if required:
        st.markdown("#### This vacancy requires")
        for item in required:
            st.markdown(f"- {item}")

    def _render_coverage_group(label: str, items: list[dict[str, object]], kind: str) -> None:
        st.markdown(f"#### {label}")
        if not items:
            st.caption("—")
            return

        for item in items:
            requirement = str(item.get("requirement") or "Requirement")
            reason = str(item.get("reason") or "—")
            scope = str(item.get("scope") or "—")
            severity = str(item.get("severity") or "—")
            evidence_ids = [str(value) for value in (item.get("evidence_ids") or []) if str(value).strip()]
            supporting_evidence = item.get("supporting_evidence") or []

            with st.container(border=True):
                if kind == "strong":
                    st.success(requirement)
                elif kind == "medium":
                    st.warning(requirement)
                else:
                    st.info(requirement)
                st.caption(f"scope: {scope} · severity: {severity}")
                st.caption(f"reason: {reason}")
                st.caption(
                    "evidence_ids: " + (", ".join(evidence_ids) if evidence_ids else "—")
                )

                if supporting_evidence:
                    with st.expander("Supporting evidence", expanded=False):
                        for evidence in supporting_evidence:
                            title = str(evidence.get("title") or "Evidence").strip()
                            evidence_id = str(evidence.get("evidence_id") or "").strip() or "—"
                            score = evidence.get("score")
                            fact_status = str(evidence.get("fact_status") or "—")
                            evidence_strength = str(evidence.get("evidence_strength") or "—")
                            st.markdown(f"**{title}**")
                            st.caption(f"evidence_id: {evidence_id}")
                            st.caption(
                                f"score: {round(float(score)) if score is not None else '—'} · "
                                f"fact_status: {fact_status} · strength: {evidence_strength}"
                            )
                            star_preview = evidence.get("star_preview") or {}
                            if isinstance(star_preview, dict) and star_preview:
                                st.caption(
                                    "STAR preview: "
                                    + ", ".join(
                                        f"{key}={value}"
                                        for key, value in star_preview.items()
                                        if value not in (None, "", [])
                                    )
                                )
                            snippet_text = str(evidence.get("snippet_text") or "").strip()
                            if snippet_text:
                                st.write(snippet_text)

    _render_coverage_group("Strong evidence", coverage.get("strong") or [], "strong")
    _render_coverage_group("Medium evidence", coverage.get("medium") or [], "medium")
    _render_coverage_group("No confirmed evidence", coverage.get("missing") or [], "missing")


def render_resume_generation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("7. Генерация адаптированного резюме")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_analysis = st.session_state.vacancy_analysis
    if not vacancy_analysis:
        st.info("Сначала проанализируйте вакансию на шаге 6.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")

    match_score = vacancy_analysis.get("match_score")
    if match_score is not None:
        st.metric("Match score перед генерацией", match_score)

    st.warning(
        "Резюме будет создано как draft. Перед использованием его нужно проверить и подтвердить человеком."
    )

    if st.button("Сгенерировать адаптированное резюме", type="primary", use_container_width=True):
        try:
            result = client.post_json("/documents/resumes/generate",
                {
                    "vacancy_id": vacancy_id,
                }, token=token)
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

        st.session_state.generated_resume = result
        st.session_state.generated_cover_letter = None
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Адаптированное резюме сгенерировано")

    if st.session_state.generated_resume:
        resume = st.session_state.generated_resume

        st.markdown("### Сгенерированное резюме")
        st.json(
            {
                "document_id": resume.get("document_id"),
                "vacancy_id": resume.get("vacancy_id"),
                "review_status": resume.get("review_status"),
                "version_label": resume.get("version_label"),
                "created_at": resume.get("created_at"),
            }
        )

        preview = resume.get("rendered_text_preview")
        if preview:
            st.markdown("#### Предпросмотр")
            st.text_area(
                "Текст резюме",
                value=preview,
                height=420,
                disabled=True,
            )

        review_status = resume.get("review_status")
        if review_status == "draft":
            st.info("Статус документа: draft. Следующий шаг — проверка и подтверждение.")


def render_cover_letter_generation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("8. Генерация сопроводительного письма")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    vacancy_analysis = st.session_state.vacancy_analysis
    if not vacancy_analysis:
        st.info("Сначала проанализируйте вакансию на шаге 6.")
        return

    generated_resume = st.session_state.generated_resume
    if not generated_resume:
        st.info("Сначала сгенерируйте адаптированное резюме на шаге 7.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")

    match_score = vacancy_analysis.get("match_score")
    if match_score is not None:
        st.metric("Match score перед генерацией письма", match_score)

    st.warning(
        "Письмо будет создано как draft. Перед отправкой его нужно проверить и подтвердить человеком."
    )

    if st.button(
        "Сгенерировать сопроводительное письмо",
        type="primary",
        use_container_width=True,
    ):
        try:
            result = client.post_json("/documents/letters/generate",
                {
                    "vacancy_id": vacancy_id,
                }, token=token)
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

        st.session_state.generated_cover_letter = result
        st.session_state.approved_resume = None
        st.session_state.approved_cover_letter = None
        st.session_state.application = None
        st.success("Сопроводительное письмо сгенерировано")

    if st.session_state.generated_cover_letter:
        letter = st.session_state.generated_cover_letter

        st.markdown("### Сгенерированное сопроводительное письмо")
        st.json(
            {
                "document_id": letter.get("document_id"),
                "vacancy_id": letter.get("vacancy_id"),
                "review_status": letter.get("review_status"),
                "version_label": letter.get("version_label"),
                "created_at": letter.get("created_at"),
            }
        )

        preview = letter.get("rendered_text_preview")
        if preview:
            st.markdown("#### Предпросмотр")
            st.text_area(
                "Текст письма",
                value=preview,
                height=360,
                disabled=True,
            )

        # ---------------------------------------------------------
        # Блок: что было адаптировано в письме (gap-mitigation)
        # ---------------------------------------------------------
        with st.expander("📋 Что было адаптировано под эту вакансию", expanded=False):
            st.markdown("Письмо усилено следующими элементами:")
            matched = [s.get("keyword") for s in (vacancy_analysis.get("strengths") or []) if s.get("keyword")]
            gaps = [g.get("keyword") for g in (vacancy_analysis.get("gaps") or []) if g.get("keyword")]
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("✅ **Усилено** (есть в профиле + в вакансии)")
                for kw in matched[:5]:
                    st.markdown(f"- {kw}")
            with col2:
                st.markdown("💡 **Проактивно закрыто** (есть в вакансии, добавлен контекст)")
                for kw in gaps[:5]:
                    st.markdown(f"- {kw}")
            st.caption("Письмо не дублирует резюме, а объясняет мотивацию и релевантность.")

        review_status = letter.get("review_status")
        if review_status == "draft":
            st.info("Статус документа: draft. Следующий шаг — проверка и подтверждение.")


def render_document_approval_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("9. Проверка и подтверждение документов")
    render_document_review_workspace_tab(
        client,
        token=token,
        selection_state_key="document_review_workspace_step9_selection",
    )


def render_application_creation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("10. Создание записи отклика")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    approved_resume = st.session_state.approved_resume
    if not approved_resume:
        st.info("Сначала подтвердите резюме на шаге 9.")
        return

    approved_cover_letter = st.session_state.approved_cover_letter
    if not approved_cover_letter:
        st.info("Сначала подтвердите сопроводительное письмо на шаге 9.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В результате импорта вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    resume_document_id = approved_resume.get("document_id")
    cover_letter_document_id = approved_cover_letter.get("document_id")

    if not resume_document_id:
        st.error("В подтверждённом резюме не найден document_id.")
        st.json(approved_resume)
        return

    if not cover_letter_document_id:
        st.error("В подтверждённом письме не найден document_id.")
        st.json(approved_cover_letter)
        return

    if approved_resume.get("review_status") != "approved" or not approved_resume.get("is_active"):
        st.warning("Резюме ещё не подтверждено или не активно.")
        return

    if (
        approved_cover_letter.get("review_status") != "approved"
        or not approved_cover_letter.get("is_active")
    ):
        st.warning("Сопроводительное письмо ещё не подтверждено или не активно.")
        return

    st.caption(f"vacancy_id: {vacancy_id}")
    st.caption(f"resume_document_id: {resume_document_id}")
    st.caption(f"cover_letter_document_id: {cover_letter_document_id}")

    st.warning(
        "Будет создана только внутренняя запись отклика в статусе draft. "
        "Автоматическая отправка на HH или другую площадку не выполняется."
    )

    notes = st.text_area(
        "Заметка к отклику",
        value="Создано через Streamlit UI. Отклик ещё не отправлен.",
        height=90,
    )

    if st.button("Создать запись отклика", type="primary", use_container_width=True):
        try:
            result = client.post_json("/applications",
                {
                    "vacancy_id": vacancy_id,
                    "resume_document_id": resume_document_id,
                    "cover_letter_document_id": cover_letter_document_id,
                    "notes": notes.strip() or None,
                }, token=token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                st.warning("Отклик для этой вакансии уже существует. Дубликат не создан.")
                st.code(exc.response.text)
                return

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

        st.session_state.application = result
        st.success("Запись отклика создана")

    if st.session_state.application:
        application = st.session_state.application

        st.markdown("### Созданная запись отклика")
        st.json(
            {
                "application_id": application.get("id"),
                "vacancy_id": application.get("vacancy_id"),
                "resume_document_id": application.get("resume_document_id"),
                "cover_letter_document_id": application.get("cover_letter_document_id"),
                "status": application.get("status"),
                "source": application.get("source"),
                "applied_at": application.get("applied_at"),
                "notes": application.get("notes"),
                "created_at": application.get("created_at"),
            }
        )

        if application.get("status") == "draft":
            st.info(
                "Отклик создан в статусе draft. Это не означает отправку. "
                "После ручной отправки на HH статус можно будет изменить на applied отдельным шагом."
            )


def render_application_status_update_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("11. Отметка ручной отправки отклика")

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    application_id = application.get("id")
    if not application_id:
        st.error("В записи отклика не найден application_id.")
        st.json(application)
        return

    current_status = application.get("status")
    st.caption(f"application_id: {application_id}")
    st.caption(f"current_status: {current_status}")

    try:
        workflow = client.get_json(f"/applications/{application_id}/workflow", token=token)
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

    if not isinstance(workflow, dict):
        st.error("Backend вернул неожиданный формат workflow metadata")
        st.json(workflow)
        return

    if current_status == "applied":
        st.success("Отклик уже отмечен как отправленный.")
        st.json(
            {
                "application_id": application.get("id"),
                "status": application.get("status"),
                "applied_at": application.get("applied_at"),
                "notes": application.get("notes"),
            }
        )
        return

    if not workflow.get("can_submit"):
        st.info(
            "Ручная отметка отправки недоступна для текущего статуса. "
            "Backend сам определяет, когда submit доступен."
        )
        with st.expander("Workflow metadata", expanded=False):
            st.json(workflow)
        return

    st.warning(
        "Нажимайте эту кнопку только после того, как вы вручную отправили отклик на HH "
        "или другой площадке. Система сама ничего не отправляет."
    )

    external_link = st.text_input(
        "Ссылка на отклик",
        value=application.get("external_link") or "",
        help="Опционально. Можно вставить ссылку на HH или другую площадку.",
    )

    if st.button(
        "Отметить как отправленный вручную",
        type="primary",
        use_container_width=True,
    ):
        try:
            result = client.post_json(f"/applications/{application_id}/submit",
                {
                    "source": "manual",
                    "external_link": external_link.strip() or None,
                }, token=token)
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

        st.session_state.application = result
        st.success("Отклик отмечен как отправленный")

    if st.session_state.application:
        updated_application = st.session_state.application

        st.markdown("### Текущий статус отклика")
        st.json(
            {
                "application_id": updated_application.get("id"),
                "vacancy_id": updated_application.get("vacancy_id"),
                "status": updated_application.get("status"),
                "applied_at": updated_application.get("applied_at"),
                "notes": updated_application.get("notes"),
                "updated_at": updated_application.get("updated_at"),
            }
        )


def render_interview_preparation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("13. Interview Prep Workspace")
    st.caption(
        "Новый deterministic prep-слой вынесен в отдельный workspace. "
        "Здесь остался короткий вход без дублирования логики ответов на mock interview."
    )

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    if application.get("status") != "applied":
        st.info(
            "Interview prep имеет смысл запускать после ручной отправки отклика "
            "и перевода статуса в applied на шаге 11."
        )
        return

    st.caption(f"application_id: {application.get('id')}")
    st.caption(f"vacancy_id: {application.get('vacancy_id')}")

    render_interview_prep_workspace_tab(
        client,
        token=token,
        selection_state_key="interview_prep_workspace_flow_selection",
    )


def render_application_dashboard(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("Дашборд откликов")
    st.caption(
        "Список внутренних записей откликов. Это не отправляет отклики на HH и не выполняет внешних действий."
    )

    status_labels = {
        "draft": "Черновик",
        "ready": "Готов к отправке",
        "applied": "Отправлен вручную",
        "screening": "Скрининг",
        "interview": "Интервью",
        "rejected": "Отказ",
        "offer": "Оффер",
        "withdrawn": "Отозван",
    }

    try:
        applications = client.get_json("/applications", token=token)
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

    if not isinstance(applications, list):
        st.error("Backend вернул неожиданный формат списка откликов")
        st.json(applications)
        return

    if not applications:
        st.info("Пока нет созданных откликов.")
        return

    applications_by_id = {
        str(application.get("id")): application
        for application in applications
        if application.get("id")
    }

    try:
        reminders = client.get_application_reminders(token=token)
    except Exception:
        reminders = None

    if isinstance(reminders, list) and reminders:
        reminder_counts: dict[str, int] = {}
        for reminder in reminders:
            reminder_type = str(reminder.get("reminder_type") or "unknown")
            reminder_counts[reminder_type] = reminder_counts.get(reminder_type, 0) + 1

        st.warning("⚠ Требует внимания")

        for reminder_type, count in reminder_counts.items():
            if reminder_type == "follow_up_missing":
                st.markdown(f"- {count} откликов ждут follow-up больше 14 дней")
            elif reminder_type == "ready_not_submitted":
                st.markdown(f"- {count} готовых откликов не отправлены")
            elif reminder_type == "draft_stale":
                st.markdown(f"- {count} черновиков без активности")
            else:
                label = APPLICATION_REMINDER_LABELS.get(reminder_type, reminder_type)
                st.markdown(f"- {count} {label.lower()}")

        reminder_rows = []
        for reminder in reminders:
            application_id = str(reminder.get("application_id") or "")
            application = applications_by_id.get(application_id, {})
            reminder_rows.append(
                {
                    "Type": APPLICATION_REMINDER_LABELS.get(
                        str(reminder.get("reminder_type") or ""),
                        str(reminder.get("reminder_type") or ""),
                    ),
                    "Vacancy": format_vacancy_title(application.get("vacancy_title")),
                    "Age": f"{reminder.get('days_since_event', 0)}d",
                }
            )

        st.dataframe(
            reminder_rows,
            use_container_width=True,
            hide_index=True,
        )

    try:
        analytics = client.get_json("/applications/analytics/summary", token=token)
    except Exception:
        analytics = None

    if isinstance(analytics, dict):
        col_total, col_applied, col_conversion, col_avg, col_offer, col_rejected = st.columns(6)

        with col_total:
            st.metric("Всего откликов", analytics.get("total_applications", 0))

        with col_applied:
            count_by_status = analytics.get("count_by_status") or {}
            st.metric(
                "Отправлены+",
                sum(
                    count_by_status.get(status, 0)
                    for status in [
                        "applied",
                        "screening",
                        "interview",
                        "offer",
                        "rejected",
                        "withdrawn",
                    ]
                ),
            )

        with col_conversion:
            conversion_to_applied = analytics.get("conversion_to_applied") or 0
            st.metric("Conversion to applied", f"{round(conversion_to_applied * 100)}%")

        with col_avg:
            avg = analytics.get("average_time_to_apply_hours")
            st.metric("Avg time to apply", f"{avg}h" if avg is not None else "—")

        with col_offer:
            st.metric("Офферы", analytics.get("offers_count", 0))

        with col_rejected:
            st.metric("Отказы", analytics.get("rejections_count", 0))

    counts_by_status = {
        "draft": 0,
        "ready": 0,
        "applied": 0,
        "screening": 0,
        "interview": 0,
        "rejected": 0,
        "offer": 0,
        "withdrawn": 0,
    }

    for application in applications:
        status_value = application.get("status")
        if status_value in counts_by_status:
            counts_by_status[status_value] += 1

    metric_cols = st.columns(8)

    for col, status_value in zip(metric_cols, counts_by_status.keys()):
        with col:
            st.metric(
                status_labels.get(status_value, status_value),
                counts_by_status[status_value],
            )

    table_rows = []
    for application in applications:
        status_value = application.get("status")
        table_rows.append(
            {
                "Вакансия": format_vacancy_title(application.get("vacancy_title")),
                "Компания": format_vacancy_company(application.get("vacancy_company")),
                "Локация": format_vacancy_location(application.get("vacancy_location")),
                "Статус": format_application_status(status_value),
                "Дата отправки": format_optional_datetime(application.get("applied_at")),
                "Результат": format_application_outcome(application.get("outcome")),
                "Создано": format_optional_datetime(application.get("created_at")),
                "Заметки": application.get("notes") or "—",
            }
        )

    st.markdown("### Список откликов")
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
    )

    application_ids = [
        str(application.get("id"))
        for application in applications
        if application.get("id")
    ]

    if not application_ids:
        st.warning("В списке откликов нет корректных application_id.")
        return

    applications_by_id = {
        str(application.get("id")): application
        for application in applications
        if application.get("id")
    }

    selected_application_id = st.selectbox(
        "Выберите отклик для просмотра и обновления статуса",
        options=application_ids,
        format_func=lambda value: (
            f"{status_labels.get(applications_by_id[value].get('status'), applications_by_id[value].get('status'))} "
            f"· {value[:8]} "
            f"· {applications_by_id[value].get('created_at') or ''}"
        ),
    )

    if not selected_application_id:
        return

    try:
        selected_application = client.get_json(f"/applications/{selected_application_id}", token=token)
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

    if not isinstance(selected_application, dict):
        st.error("Backend вернул неожиданный формат отклика")
        st.json(selected_application)
        return

    st.markdown("### Детали отклика")
    st.json(
        {
            "application_id": selected_application.get("id"),
            "vacancy_id": selected_application.get("vacancy_id"),
            "resume_document_id": selected_application.get("resume_document_id"),
            "cover_letter_document_id": selected_application.get("cover_letter_document_id"),
            "status": selected_application.get("status"),
            "source": selected_application.get("source"),
            "applied_at": selected_application.get("applied_at"),
            "outcome": selected_application.get("outcome"),
            "notes": selected_application.get("notes"),
            "created_at": selected_application.get("created_at"),
            "updated_at": selected_application.get("updated_at"),
        }
    )

    vacancy_id_for_fit = str(selected_application.get("vacancy_id") or "").strip()
    if vacancy_id_for_fit:
        st.divider()
        _render_vacancy_intelligence_block(client, vacancy_id=vacancy_id_for_fit, token=token)

    st.markdown("### История статусов")
    timeline: list[dict[str, object]] = []
    try:
        timeline_result = client.get_json(
            f"/applications/{selected_application_id}/timeline",
            token=token,
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code} при загрузке timeline")
        st.code(exc.response.text)
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend для загрузки timeline")
        st.code(str(exc))
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ для timeline")
        st.code(str(exc))
    else:
        if not isinstance(timeline_result, list):
            st.error("Backend вернул неожиданный формат timeline")
            st.json(timeline_result)
        else:
            timeline = timeline_result

    if timeline:
        for item in timeline:
            previous_status = item.get("previous_status") or "—"
            new_status = item.get("new_status") or "—"
            changed_at = format_optional_datetime(item.get("changed_at"))

            with st.container(border=True):
                st.markdown(f"**{changed_at}**")
                st.write(f"{previous_status} -> {new_status}")
                if item.get("notes"):
                    st.caption(item.get("notes"))
    else:
        st.caption("История статусов пока пуста.")

    st.markdown("### Activity log")
    activity_log: list[dict[str, object]] = []
    try:
        activity_log_result = client.get_json(
            f"/applications/{selected_application_id}/activity-log",
            token=token,
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code} при загрузке activity log")
        st.code(exc.response.text)
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend для загрузки activity log")
        st.code(str(exc))
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ для activity log")
        st.code(str(exc))
    else:
        if not isinstance(activity_log_result, list):
            st.error("Backend вернул неожиданный формат activity log")
            st.json(activity_log_result)
        else:
            activity_log = activity_log_result

    def _render_activity_meta(meta_json: dict[str, object] | None) -> None:
        if not meta_json:
            st.caption("meta: —")
            return

        important_keys = [
            "vacancy_id",
            "resume_document_id",
            "cover_letter_document_id",
            "previous_status",
            "new_status",
            "source",
            "external_link",
            "applied_at",
        ]
        important_parts = []
        for key in important_keys:
            value = meta_json.get(key)
            if value not in (None, "", []):
                important_parts.append(f"{key}={value}")

        if important_parts:
            st.caption("meta: " + ", ".join(important_parts))
        else:
            st.caption("meta: " + ", ".join(f"{key}={value}" for key, value in meta_json.items()))

    if activity_log:
        for item in activity_log:
            with st.container(border=True):
                st.markdown(f"**{item.get('title') or item.get('event_type') or 'Event'}**")
                st.caption(format_optional_datetime(item.get("created_at")))
                if item.get("description"):
                    st.write(item.get("description"))
                _render_activity_meta(item.get("meta_json") or {})
    else:
        st.caption("Activity log пока пуст.")

    current_status = str(selected_application.get("status") or "").strip().lower()

    try:
        workflow = client.get_json(f"/applications/{selected_application_id}/workflow", token=token)
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

    if not isinstance(workflow, dict):
        st.error("Backend вернул неожиданный формат workflow metadata")
        st.json(workflow)
        return

    allowed_transitions = workflow.get("allowed_transitions") or []
    next_statuses = [
        str(item.get("status") or "").strip()
        for item in allowed_transitions
        if isinstance(item, dict) and str(item.get("status") or "").strip()
    ]
    transition_labels = {
        str(item.get("status") or "").strip(): str(item.get("label") or "").strip()
        for item in allowed_transitions
        if isinstance(item, dict) and str(item.get("status") or "").strip()
    }

    st.markdown("### Ручное обновление статуса")

    if not next_statuses:
        st.info(
            "Для текущего статуса нет разрешённых следующих переходов. "
            "Финальные статусы не переоткрываются автоматически."
        )
        with st.expander("Workflow metadata", expanded=False):
            st.json(workflow)
        return

    with st.form(f"application_status_dashboard_form_{selected_application_id}"):
        next_status = st.selectbox(
            "Новый статус",
            options=next_statuses,
            format_func=lambda value: transition_labels.get(value, status_labels.get(value, value)),
        )

        notes = st.text_area(
            "Заметка к изменению статуса",
            value="Статус обновлён вручную через Streamlit dashboard.",
            height=90,
        )

        submitted = st.form_submit_button(
            "Сохранить новый статус",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            updated_application = client.patch_json(f"/applications/{selected_application_id}/status",
                {
                    "status": next_status,
                    "notes": notes.strip() or None,
                }, token=token)
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

        if not isinstance(updated_application, dict):
            st.error("Backend вернул неожиданный формат отклика")
            st.json(updated_application)
            return

        st.success("Статус отклика обновлён")
        st.rerun()


def render_mvp_flow(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("MVP-сценарий")

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

    st.info(
        "После создания и ручной отправки отклика используйте вкладку «Отклики» "
        "для дальнейшего workflow, analytics и tracking."
    )

    st.divider()

    render_interview_preparation_step(client, token=token)

    st.divider()

    st.success(
        "Сквозной MVP-сценарий во frontend подключён: резюме → вакансия → документы → "
        "ручной отклик → подготовка к интервью."
    )


def main() -> None:
    init_session_state()
    _, client, token = render_sidebar()

    tab_home, tab_flow, tab_review, tab_prep, tab_evidence, tab_strategy, tab_applications = st.tabs(
        [
            "Главная",
            "MVP-сценарий",
            "Document Review Workspace",
            "Interview Prep Workspace",
            "Evidence Workspace",
            "Career Strategy",
            "Отклики",
        ]
    )

    with tab_home:
        render_home()

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

    with tab_evidence:
        render_evidence_workspace_tab(client, token=token)

    with tab_strategy:
        render_career_strategy_workspace_tab(client, token=token)

    with tab_applications:
        render_application_dashboard(client, token=token)


if __name__ == "__main__":
    main()
