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

INTERVIEW_STATUS_LABELS = {
    "draft": "Черновик",
    "answered": "С ответами",
}

QUESTION_TYPE_LABELS = {
    "role_overview": "Обзор роли",
    "must_have_requirement": "Обязательное требование",
    "gap_preparation": "Подготовка по gap-зоне",
    "strength_deep_dive": "Разбор сильной стороны",
    "achievement_star_story": "STAR-история по достижению",
}

ANSWER_FORMAT_LABELS = {
    "short_structured": "Короткий структурированный ответ",
    "STAR_or_example": "STAR или конкретный пример",
    "honest_gap_response": "Честный ответ по gap-зоне",
    "STAR": "STAR",
}

APPLICATION_OUTCOME_LABELS = {
    "rejected": "Отказ",
    "offer": "Оффер",
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


def format_interview_status(value: str | None) -> str:
    if not value:
        return "—"
    return INTERVIEW_STATUS_LABELS.get(value, value)


def format_question_type(value: str | None) -> str:
    if not value:
        return "—"
    return QUESTION_TYPE_LABELS.get(value, value)


def format_answer_format(value: str | None) -> str:
    if not value:
        return "—"
    return ANSWER_FORMAT_LABELS.get(value, value)


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
    if "application_list" not in st.session_state:
        st.session_state.application_list = None
    if "interview_session" not in st.session_state:
        st.session_state.interview_session = None
    if "interview_answers_result" not in st.session_state:
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
                st.session_state.interview_session = None
                st.session_state.interview_answers_result = None

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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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

    generated_resume = st.session_state.generated_resume
    if not generated_resume:
        st.info("Сначала сгенерируйте адаптированное резюме на шаге 7.")
        return

    generated_cover_letter = st.session_state.generated_cover_letter
    if not generated_cover_letter:
        st.info("Сначала сгенерируйте сопроводительное письмо на шаге 8.")
        return

    resume_document_id = generated_resume.get("document_id")
    cover_letter_document_id = generated_cover_letter.get("document_id")

    if not resume_document_id:
        st.error("В сгенерированном резюме не найден document_id.")
        st.json(generated_resume)
        return

    if not cover_letter_document_id:
        st.error("В сгенерированном письме не найден document_id.")
        st.json(generated_cover_letter)
        return

    col_resume, col_letter = st.columns(2)

    with col_resume:
        st.markdown("### Резюме")
        st.caption(f"document_id: {resume_document_id}")
        st.caption(f"status: {generated_resume.get('review_status')}")

        resume_preview = generated_resume.get("rendered_text_preview")
        if resume_preview:
            with st.expander("Предпросмотр резюме", expanded=False):
                st.text(resume_preview)

    with col_letter:
        st.markdown("### Сопроводительное письмо")
        st.caption(f"document_id: {cover_letter_document_id}")
        st.caption(f"status: {generated_cover_letter.get('review_status')}")

        letter_preview = generated_cover_letter.get("rendered_text_preview")
        if letter_preview:
            with st.expander("Предпросмотр письма", expanded=False):
                st.text(letter_preview)

    st.warning(
        "Подтверждение означает, что человек проверил документы и разрешает использовать их "
        "для создания записи отклика. Автоматическая отправка отклика не выполняется."
    )

    review_comment = st.text_area(
        "Комментарий к проверке",
        value="Проверено и подтверждено пользователем через Streamlit UI.",
        height=90,
    )

    if st.button(
        "Подтвердить резюме и сопроводительное письмо",
        type="primary",
        use_container_width=True,
    ):
        try:
            approved_resume = client.patch_json(f"/documents/{resume_document_id}/review",
                {
                    "review_status": "approved",
                    "review_comment": review_comment.strip() or None,
                    "set_active_when_approved": True,
                }, token=token)

            approved_cover_letter = client.patch_json(f"/documents/{cover_letter_document_id}/review",
                {
                    "review_status": "approved",
                    "review_comment": review_comment.strip() or None,
                    "set_active_when_approved": True,
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

        if not isinstance(approved_resume, dict):
            st.error("Backend вернул неожиданный формат ответа для резюме")
            st.json(approved_resume)
            return

        if not isinstance(approved_cover_letter, dict):
            st.error("Backend вернул неожиданный формат ответа для письма")
            st.json(approved_cover_letter)
            return

        st.session_state.approved_resume = approved_resume
        st.session_state.approved_cover_letter = approved_cover_letter
        st.session_state.application = None
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None

        st.success("Документы подтверждены")

    if st.session_state.approved_resume and st.session_state.approved_cover_letter:
        st.markdown("### Подтверждённые документы")

        col_approved_resume, col_approved_letter = st.columns(2)

        with col_approved_resume:
            st.markdown("#### Резюме")
            st.json(
                {
                    "document_id": st.session_state.approved_resume.get("document_id"),
                    "document_kind": st.session_state.approved_resume.get("document_kind"),
                    "review_status": st.session_state.approved_resume.get("review_status"),
                    "is_active": st.session_state.approved_resume.get("is_active"),
                    "updated_at": st.session_state.approved_resume.get("updated_at"),
                }
            )

        with col_approved_letter:
            st.markdown("#### Сопроводительное письмо")
            st.json(
                {
                    "document_id": st.session_state.approved_cover_letter.get("document_id"),
                    "document_kind": st.session_state.approved_cover_letter.get("document_kind"),
                    "review_status": st.session_state.approved_cover_letter.get("review_status"),
                    "is_active": st.session_state.approved_cover_letter.get("is_active"),
                    "updated_at": st.session_state.approved_cover_letter.get("updated_at"),
                }
            )

        st.info("Следующий шаг — создать запись отклика без автоматической отправки.")

        st.markdown("### Экспорт документов")

        approved_resume_id = st.session_state.approved_resume.get("document_id")
        approved_cover_letter_id = st.session_state.approved_cover_letter.get("document_id")

        if approved_resume_id and approved_cover_letter_id:
            try:
                resume_txt = client.get_text(f"/documents/{approved_resume_id}/export/txt", token=token)
                resume_md = client.get_text(f"/documents/{approved_resume_id}/export/md", token=token)
                resume_docx = client.get_bytes(
                    f"/documents/{approved_resume_id}/export/docx", token=token)
                cover_letter_txt = client.get_text(
                    f"/documents/{approved_cover_letter_id}/export/txt", token=token)
                cover_letter_md = client.get_text(
                    f"/documents/{approved_cover_letter_id}/export/md", token=token)
                cover_letter_docx = client.get_bytes(
                    f"/documents/{approved_cover_letter_id}/export/docx", token=token)
            except httpx.HTTPStatusError as exc:
                st.error(f"Backend вернул ошибку HTTP {exc.response.status_code} при экспорте")
                st.code(exc.response.text)
            except httpx.RequestError as exc:
                st.error("Не удалось подключиться к backend для экспорта")
                st.code(str(exc))
            else:
                col_resume_export, col_letter_export = st.columns(2)

                with col_resume_export:
                    st.markdown("#### Резюме")
                    st.download_button(
                        "Скачать резюме TXT",
                        data=resume_txt,
                        file_name="resume.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )
                    st.download_button(
                        "Скачать резюме MD",
                        data=resume_md,
                        file_name="resume.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                    st.download_button(
                        "Скачать резюме DOCX",
                        data=resume_docx,
                        file_name="resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )

                with col_letter_export:
                    st.markdown("#### Сопроводительное письмо")
                    st.download_button(
                        "Скачать письмо TXT",
                        data=cover_letter_txt,
                        file_name="cover_letter.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )
                    st.download_button(
                        "Скачать письмо MD",
                        data=cover_letter_md,
                        file_name="cover_letter.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                    st.download_button(
                        "Скачать письмо DOCX",
                        data=cover_letter_docx,
                        file_name="cover_letter.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
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
        st.session_state.application_list = None
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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
        st.session_state.application_list = None
        st.session_state.interview_session = None
        st.session_state.interview_answers_result = None
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


def render_application_dashboard_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("12. Дашборд откликов")

    st.caption(
        "Список внутренних записей откликов. Это не список реальных откликов на HH, "
        "а локальный трекер статусов внутри проекта."
    )

    if st.button(
        "Обновить список откликов",
        type="primary",
        use_container_width=True,
        key="refresh_application_dashboard",
    ):
        try:
            result = client.get_json("/applications", token=token)
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

        if not isinstance(result, list):
            st.error("Backend вернул неожиданный формат списка откликов")
            st.json(result)
            return

        st.session_state.application_list = result

    applications = st.session_state.application_list

    if applications is None:
        st.info("Нажмите кнопку обновления, чтобы загрузить список откликов.")
        return

    if not applications:
        st.info("Пока нет созданных записей откликов.")
        return

    status_counts: dict[str, int] = {}
    for item in applications:
        status_value = str(item.get("status") or "unknown")
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

    col_total, col_draft, col_ready, col_applied, col_screening, col_interview, col_final = st.columns(7)

    with col_total:
        st.metric("Всего", len(applications))

    with col_draft:
        st.metric("Черновики", status_counts.get("draft", 0))

    with col_ready:
        st.metric("Готовы", status_counts.get("ready", 0))

    with col_applied:
        st.metric("Отправлены", status_counts.get("applied", 0))

    with col_screening:
        st.metric("Скрининг", status_counts.get("screening", 0))

    with col_interview:
        st.metric("Интервью", status_counts.get("interview", 0))

    with col_final:
        st.metric(
            "Финальные",
            status_counts.get("rejected", 0)
            + status_counts.get("offer", 0)
            + status_counts.get("withdrawn", 0),
        )

    rows = []
    for item in applications:
        rows.append(
            {
                "Вакансия": format_vacancy_title(item.get("vacancy_title")),
                "Компания": format_vacancy_company(item.get("vacancy_company")),
                "Локация": format_vacancy_location(item.get("vacancy_location")),
                "Статус": format_application_status(item.get("status")),
                "Источник": item.get("source") or "—",
                "Дата отправки": format_optional_datetime(item.get("applied_at")),
                "Outcome": item.get("outcome") or "—",
                "Заметки": item.get("notes") or "—",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Технические детали откликов", expanded=False):
        for index, item in enumerate(applications, start=1):
            st.markdown(
                f"#### {index}. {item.get('vacancy_title') or item.get('vacancy_id')}"
            )
            st.json(
                {
                    "application_id": item.get("id"),
                    "vacancy_id": item.get("vacancy_id"),
                    "resume_document_id": item.get("resume_document_id"),
                    "cover_letter_document_id": item.get("cover_letter_document_id"),
                    "status": item.get("status"),
                    "source": item.get("source"),
                    "applied_at": item.get("applied_at"),
                    "outcome": item.get("outcome"),
                    "notes": item.get("notes"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )


def render_interview_preparation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("13. Подготовка к собеседованию")

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    if application.get("status") != "applied":
        st.info(
            "Подготовку к интервью лучше создавать после того, как отклик вручную отправлен "
            "и отмечен как applied на шаге 11."
        )
        return

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Не найдена вакансия в текущей сессии Streamlit.")
        return

    vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    if not vacancy_id:
        st.error("В вакансии не найден vacancy_id.")
        st.json(vacancy)
        return

    st.caption(f"vacancy_id: {vacancy_id}")
    st.caption(f"application_id: {application.get('id')}")

    st.warning(
        "Будет создана внутренняя сессия подготовки к интервью. "
        "Это не отправляет данные работодателю и не выполняет внешних действий."
    )

    if st.button("Создать подготовку к интервью", type="primary", use_container_width=True):
        try:
            result = client.post_json("/interviews/sessions",
                {
                    "vacancy_id": vacancy_id,
                    "session_type": "vacancy",
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

        st.session_state.interview_session = result
        st.session_state.interview_answers_result = None
        st.success("Подготовка к интервью создана")

    interview_session = st.session_state.interview_session
    if not interview_session:
        return

    session_id = interview_session.get("id")
    question_set = interview_session.get("question_set") or []
    question_types = sorted(
        {
            str(question.get("type"))
            for question in question_set
            if question.get("type")
        }
    )

    st.markdown("### Сессия подготовки")

    st.json(
        {
            "interview_session_id": session_id,
            "vacancy_id": interview_session.get("vacancy_id"),
            "status": interview_session.get("status"),
            "question_count": len(question_set),
            "question_types": [format_question_type(value) for value in question_types],
        }
    )

    if not session_id:
        st.error("В interview session не найден id.")
        st.json(interview_session)
        return

    if not question_set:
        st.warning("Backend не вернул список вопросов.")
        return

    with st.expander("Список вопросов", expanded=False):
        for index, question in enumerate(question_set, start=1):
            question_type = question.get("type")
            prompt = question.get("prompt")
            answer_format = question.get("answer_format")

            st.markdown(f"**{index}. {format_question_type(question_type)}**")
            st.write(localize_demo_ui_text(prompt))
            if answer_format:
                st.caption(f"Формат ответа: {format_answer_format(answer_format)}")

    st.markdown("### Ответы на вопросы интервью")

    st.info(
        "Можно заполнить часть ответов и сохранить промежуточный результат. "
        "Для STAR-вопросов используйте структуру: Ситуация / Задача / Действия / Результат."
    )

    default_answers = {
        0: (
            "Меня интересует эта роль, потому что она соответствует моему направлению: "
            "Python и backend-разработка."
        ),
        1: (
            "Ситуация: я работал над практическим Python-проектом. "
            "Задача: собрать рабочий прототип. "
            "Действия: реализовал backend-flow. "
            "Результат: прототип был готов к проверке."
        ),
    }

    with st.form(f"interview_answers_form_{session_id}"):
        answers_payload: list[dict] = []

        for question_index, question in enumerate(question_set):
            question_number = question_index + 1
            question_type = question.get("type") or "unknown"
            prompt = question.get("prompt") or f"Вопрос {question_number}"
            answer_format = question.get("answer_format")

            st.markdown(f"#### Вопрос {question_number}: {format_question_type(question_type)}")
            st.write(localize_demo_ui_text(prompt))

            if answer_format:
                st.caption(f"Формат ответа: {format_answer_format(answer_format)}")

            answer_text = st.text_area(
                f"Ответ {question_number}",
                value=localize_demo_ui_text(default_answers.get(question_index, "")),
                height=150,
                key=f"interview_answer_{session_id}_{question_index}",
            )

            if answer_text.strip():
                answers_payload.append(
                    {
                        "question_index": question_index,
                        "answer_text": answer_text.strip(),
                    }
                )

        submitted = st.form_submit_button(
            "Сохранить ответы и получить обратную связь",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not answers_payload:
            st.error("Нужно заполнить хотя бы один ответ.")
            return

        try:
            result = client.patch_json(f"/interviews/sessions/{session_id}/answers",
                {
                    "answers": answers_payload,
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

        st.session_state.interview_session = result
        st.session_state.interview_answers_result = result
        st.success("Ответы сохранены, обратная связь рассчитана")

    if st.session_state.interview_answers_result:
        answered = st.session_state.interview_answers_result

        st.markdown("### Результат подготовки")

        score = answered.get("score") or {}
        feedback = answered.get("feedback") or {}
        feedback_items = feedback.get("items") or []

        question_count = int(score.get("question_count") or len(question_set) or 0)
        answered_count = int(score.get("answered_count") or 0)
        unanswered_count = int(score.get("unanswered_count") or 0)
        warning_count = int(score.get("warning_count") or 0)
        readiness_score = score.get("readiness_score")

        col_status, col_answered, col_unanswered, col_warnings, col_score = st.columns(5)

        with col_status:
            st.metric("Статус", format_interview_status(answered.get("status")))

        with col_answered:
            st.metric("Ответов", f"{answered_count} / {question_count}")

        with col_unanswered:
            st.metric("Осталось", unanswered_count)

        with col_warnings:
            st.metric("Предупреждений", warning_count)

        with col_score:
            st.metric(
                "Готовность",
                f"{readiness_score} / 100" if readiness_score is not None else "—",
            )

        if question_count > 0:
            progress_value = max(0.0, min(1.0, answered_count / question_count))
            st.progress(progress_value)

        if unanswered_count > 0:
            st.info(
                "Низкая готовность сейчас означает не плохое качество ответов, "
                "а незавершённую подготовку: заполнены не все вопросы."
            )
        elif warning_count == 0:
            st.success("Все вопросы заполнены, критичных предупреждений по ответам нет.")

        if feedback_items:
            st.markdown("#### Обратная связь по ответам")

            for item in feedback_items:
                with st.container(border=True):
                    st.markdown(
                        f"**Вопрос {int(item.get('question_index', 0)) + 1} — "
                        f"{format_question_type(item.get('question_type'))}**"
                    )
                    st.caption(f"Длина ответа: {item.get('answer_length')} символов")

                    warnings = item.get("warnings") or []
                    suggestions = item.get("suggestions") or []

                    if warnings:
                        st.warning("Предупреждения: " + ", ".join(warnings))
                    else:
                        st.success("Критичных предупреждений нет")

                    if suggestions:
                        st.markdown("Рекомендации:")
                        for suggestion in suggestions:
                            st.markdown(f"- {suggestion}")

        with st.expander("Raw JSON результата", expanded=False):
            st.json(answered)


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


def _format_mock_score(score: object) -> str:
    if score is None:
        return "—"

    try:
        value = float(score)
    except (TypeError, ValueError):
        return str(score)

    if 0.0 <= value <= 1.0:
        return f"{round(value * 100)}%"

    return f"{round(value)} / 100"


def _render_mock_evaluation_block(
    *,
    evaluation: dict,
    progress: dict | None = None,
) -> None:
    st.markdown("#### Evaluation")

    with st.container(border=True):
        col_score, col_progress = st.columns(2)

        with col_score:
            st.metric("Оценка", _format_mock_score(evaluation.get("score")))

        with col_progress:
            current_value = progress.get("current") if progress else None
            total_value = progress.get("total") if progress else None
            progress_value = (
                f"{current_value} / {total_value}"
                if current_value is not None and total_value is not None
                else "—"
            )
            st.metric("Прогресс", progress_value)

        feedback = evaluation.get("feedback") or []
        if feedback:
            st.markdown("**Что улучшить**")
            for item in feedback:
                st.markdown(f"- {item}")
        else:
            st.info("Критичных замечаний по ответу нет.")


def _render_mock_advisory_block(advisory: dict | None) -> None:
    if not advisory:
        st.info("Advisory не вернулся.")
        return

    st.markdown("#### Advisory")

    with st.container(border=True):
        sections = [
            ("Сильные стороны", advisory.get("strong_parts") or []),
            ("Чего не хватает", advisory.get("missing_signals") or []),
            ("STAR improvements", advisory.get("star_improvements") or []),
            ("Где не хватает конкретики", advisory.get("specificity_gaps") or []),
            ("Риски", advisory.get("risk_warnings") or []),
            ("Нужна верификация", advisory.get("confirmation_needed") or []),
        ]

        for title, items in sections:
            if not items:
                continue
            st.markdown(f"**{title}**")
            for item in items:
                st.markdown(f"- {item}")

        suggested_revision = (advisory.get("suggested_revision") or "").strip()
        if suggested_revision:
            st.markdown("**Suggested revision**")
            st.write(suggested_revision)


def _render_mock_summary_block(summary: dict) -> None:
    st.markdown("#### Summary")

    with st.container(border=True):
        progress = summary.get("progress") or {}
        col_status, col_answered, col_total, col_attempts, col_readiness = st.columns(5)

        with col_status:
            st.metric(
                "Статус",
                "Завершено" if progress.get("completed") else "В процессе",
            )

        with col_answered:
            st.metric("Ответов", progress.get("answered", 0))

        with col_total:
            st.metric("Всего вопросов", progress.get("total", 0))

        with col_attempts:
            st.metric("Попыток", summary.get("attempt_count", 0))

        with col_readiness:
            st.metric("Готовность", _format_mock_score(summary.get("readiness_score")))

        competency_readiness = summary.get("competency_readiness") or []
        if competency_readiness:
            st.markdown("**Готовность по компетенциям**")
            for item in competency_readiness:
                competency_name = (
                    item.get("competency_name")
                    or item.get("competency_key")
                    or "Компетенция"
                )
                readiness = item.get("readiness_score")
                answered = item.get("answered_count", 0)
                total = item.get("question_count", 0)
                warnings = item.get("warning_count", 0)

                st.markdown(
                    f"- {competency_name}: {_format_mock_score(readiness)}, "
                    f"ответов {answered} / {total}, предупреждений {warnings}"
                )

        weak_competencies = summary.get("weak_competencies") or []
        if weak_competencies:
            st.markdown("**Слабые зоны**")
            for item in weak_competencies:
                competency_name = (
                    item.get("competency_name")
                    or item.get("competency_key")
                    or "Компетенция"
                )
                st.markdown(
                    f"- {competency_name}: {_format_mock_score(item.get('readiness_score'))}"
                )


def render_interview_mock_mode(
    client: CareerCopilotApiClient,
    selected_session: dict,
    *,
    token: str | None = None,
) -> None:
    st.markdown("### Mock interview mode")

    question_set = selected_session.get("question_set") or []
    if not question_set:
        st.info("Для этой сессии нет question_set, поэтому mock interview недоступен.")
        return

    session_id = str(selected_session.get("id") or "").strip()
    if not session_id:
        st.warning("Не удалось определить session_id для mock interview.")
        return

    session_mode = str(selected_session.get("mode") or "")
    session_status = str(selected_session.get("status") or "")

    if session_status == "completed":
        try:
            summary = client.get_json(
                f"/interviews/sessions/{session_id}/mock/summary",
                token=token,
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

        if not isinstance(summary, dict):
            st.error("Backend вернул неожиданный формат mock summary")
            st.json(summary)
            return

        st.success("Mock interview completed")
        _render_mock_summary_block(summary)
        return

    current_payload = None
    if session_mode == "mock_interview":
        try:
            current_payload = client.get_json(
                f"/interviews/sessions/{session_id}/mock/current",
                token=token,
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

        if not isinstance(current_payload, dict):
            st.error("Backend вернул неожиданный формат текущего вопроса")
            st.json(current_payload)
            return
    else:
        start_clicked = st.button(
            "Начать mock interview",
            key=f"mock_interview_start_{session_id}",
            type="primary",
            use_container_width=True,
        )
        if not start_clicked:
            st.info("Нажмите кнопку, чтобы запустить mock interview для этой сессии.")
            return

        try:
            started_session = client.post_json(
                f"/interviews/sessions/{session_id}/mock/start",
                {},
                token=token,
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

        if not isinstance(started_session, dict):
            st.error("Backend вернул неожиданный формат session")
            st.json(started_session)
            return

        selected_session = started_session
        session_mode = str(selected_session.get("mode") or "")

        try:
            current_payload = client.get_json(
                f"/interviews/sessions/{session_id}/mock/current",
                token=token,
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

        if not isinstance(current_payload, dict):
            st.error("Backend вернул неожиданный формат текущего вопроса")
            st.json(current_payload)
            return

    question = current_payload.get("question") or {}
    progress = current_payload.get("progress") or {}
    question_index = current_payload.get("question_index")
    question_id = str(question.get("question_id") or "").strip()

    with st.container(border=True):
        st.metric(
            "Текущий вопрос",
            f"{progress.get('current', 0)} / {progress.get('total', 0)}",
        )
        st.caption(
            f"Question {progress.get('current', 0)} / {progress.get('total', 0)}"
        )
        st.write(question.get("prompt") or question.get("question_text") or "Вопрос")
        if question.get("answer_format"):
            st.caption(f"Формат ответа: {format_answer_format(question.get('answer_format'))}")
        total_value = int(progress.get("total") or 0)
        current_value = int(progress.get("current") or 0)
        if total_value > 0:
            st.progress(max(0.0, min(1.0, current_value / total_value)))

    answer_key = f"mock_interview_answer_{session_id}_{question_id or question_index}"
    with st.form(f"mock_interview_form_{session_id}_{question_id or question_index}"):
        answer_text = st.text_area(
            "Ответ",
            height=180,
            key=answer_key,
        )
        submitted = st.form_submit_button(
            "Отправить ответ",
            type="primary",
            use_container_width=True,
            disabled=not answer_text.strip(),
        )

    if not submitted:
        return

    if not question_id:
        st.error("Backend не вернул question_id для текущего вопроса.")
        return

    if not answer_text.strip():
        st.error("Нужно заполнить ответ перед отправкой.")
        return

    try:
        result = client.post_json(
            f"/interviews/sessions/{session_id}/mock/answer",
            {
                "question_id": question_id,
                "answer_text": answer_text.strip(),
                "include_advisory": True,
            },
            token=token,
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
        st.error("Backend вернул неожиданный формат mock answer")
        st.json(result)
        return

    st.success("Ответ отправлен")
    _render_mock_evaluation_block(
        evaluation=result.get("evaluation") or {},
        progress=result.get("progress") or {},
    )
    _render_mock_advisory_block(result.get("advisory"))

    next_question = result.get("next_question")
    if next_question:
        st.markdown("#### Следующий вопрос")
        with st.container(border=True):
            st.write(next_question.get("prompt") or next_question.get("question_text") or "Вопрос")
            if next_question.get("answer_format"):
                st.caption(
                    f"Формат ответа: {format_answer_format(next_question.get('answer_format'))}"
                )

    if result.get("completed"):
        try:
            summary = client.get_json(
                f"/interviews/sessions/{session_id}/mock/summary",
                token=token,
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

        if isinstance(summary, dict):
            st.success("Mock interview completed")
            _render_mock_summary_block(summary)
        else:
            st.error("Backend вернул неожиданный формат mock summary")
            st.json(summary)


def render_interview_dashboard(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("Интервью")
    st.caption(
        "Список внутренних сессий подготовки к интервью. "
        "Здесь можно открыть старую сессию, дозаполнить ответы и пересчитать готовность."
    )

    saved_attempt_message = st.session_state.pop(
        "interview_competency_attempt_saved_message",
        None,
    )
    if saved_attempt_message:
        st.success(saved_attempt_message)

    try:
        sessions = client.get_json("/interviews/sessions", token=token)
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

    if not isinstance(sessions, list):
        st.error("Backend вернул неожиданный формат списка interview sessions")
        st.json(sessions)
        return

    if not sessions:
        st.info("Пока нет созданных сессий подготовки к интервью.")
        return

    answered_count = sum(1 for item in sessions if item.get("status") == "answered")
    draft_count = sum(1 for item in sessions if item.get("status") == "draft")
    readiness_values = [
        int(item["readiness_score"])
        for item in sessions
        if item.get("readiness_score") is not None
    ]
    average_readiness = (
        round(sum(readiness_values) / len(readiness_values))
        if readiness_values
        else None
    )

    col_total, col_draft, col_answered, col_avg_score = st.columns(4)

    with col_total:
        st.metric("Всего сессий", len(sessions))

    with col_draft:
        st.metric("Черновики", draft_count)

    with col_answered:
        st.metric("С ответами", answered_count)

    with col_avg_score:
        st.metric(
            "Средняя готовность",
            f"{average_readiness} / 100" if average_readiness is not None else "—",
        )

    rows = []
    for item in sessions:
        rows.append(
            {
                "Вакансия": format_vacancy_title(item.get("vacancy_title")),
                "Компания": format_vacancy_company(item.get("vacancy_company")),
                "Локация": format_vacancy_location(item.get("vacancy_location")),
                "Статус": format_interview_status(item.get("status")),
                "Ответов": f"{item.get('answered_count', 0)} / {item.get('question_count', 0)}",
                "Предупреждений": item.get("warning_count", 0),
                "Готовность": (
                    f"{item.get('readiness_score')} / 100"
                    if item.get("readiness_score") is not None
                    else "—"
                ),
                "Слабые зоны": ", ".join(
                    competency.get(
                        "competency_name",
                        competency.get("competency_key", "—"),
                    )
                    for competency in (item.get("weak_competencies") or [])
                ) or "—",
                "Обновлено": format_optional_datetime(item.get("updated_at")),
            }
        )

    st.markdown("### Список подготовок")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    session_ids = [
        str(item.get("id"))
        for item in sessions
        if item.get("id")
    ]

    if not session_ids:
        st.warning("В списке нет корректных session_id.")
        return

    sessions_by_id = {
        str(item.get("id")): item
        for item in sessions
        if item.get("id")
    }

    selected_session_id = st.selectbox(
        "Выберите сессию подготовки",
        options=session_ids,
        format_func=lambda value: (
            f"{format_demo_display_text(sessions_by_id[value].get('vacancy_title'))} "
            f"· {sessions_by_id[value].get('status')} "
            f"· {value[:8]}"
        ),
    )

    if not selected_session_id:
        return

    try:
        selected_session = client.get_json(f"/interviews/sessions/{selected_session_id}", token=token)
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

    if not isinstance(selected_session, dict):
        st.error("Backend вернул неожиданный формат interview session")
        st.json(selected_session)
        return

    question_set = selected_session.get("question_set") or []
    answers = selected_session.get("answers") or []
    score = selected_session.get("score") or {}
    feedback = selected_session.get("feedback") or {}

    existing_answers_by_index = {}
    for answer in answers:
        question_index = answer.get("question_index")
        if question_index is None:
            continue
        existing_answers_by_index[int(question_index)] = answer.get("answer_text") or ""

    st.markdown("### Детали сессии")

    col_status, col_questions, col_answers, col_score = st.columns(4)

    with col_status:
        st.metric("Статус", format_interview_status(selected_session.get("status")))

    with col_questions:
        st.metric("Вопросов", len(question_set))

    with col_answers:
        st.metric("Ответов", score.get("answered_count", len(answers)))

    with col_score:
        readiness_score = score.get("readiness_score")
        st.metric(
            "Готовность",
            f"{readiness_score} / 100" if readiness_score is not None else "—",
        )

    render_interview_mock_mode(client, selected_session, token=token)

    if not question_set:
        st.warning("В этой сессии нет question_set.")
        return

    with st.expander("Список вопросов", expanded=False):
        for index, question in enumerate(question_set, start=1):
            st.markdown(f"**{index}. {format_question_type(question.get('type'))}**")
            st.write(question.get("prompt"))
            if question.get("answer_format"):
                st.caption(f"Формат ответа: {format_answer_format(question.get('answer_format'))}")

    st.markdown("### Редактор ответов")

    st.info(
        "Можно дозаполнить ответы и сохранить промежуточный результат. "
        "Пустые ответы не сохраняются. Для STAR-вопросов используйте: "
        "Ситуация / Задача / Действия / Результат."
    )

    with st.form(f"interview_dashboard_answers_form_{selected_session_id}"):
        answers_payload: list[dict] = []

        for question_index, question in enumerate(question_set):
            question_number = question_index + 1
            question_type = question.get("type") or "unknown"
            prompt = question.get("prompt") or f"Вопрос {question_number}"
            answer_format = question.get("answer_format")

            st.markdown(f"#### Вопрос {question_number}: {format_question_type(question_type)}")
            st.write(localize_demo_ui_text(prompt))

            if answer_format:
                st.caption(f"Формат ответа: {format_answer_format(answer_format)}")

            answer_text = st.text_area(
                f"Ответ {question_number}",
                value=localize_demo_ui_text(existing_answers_by_index.get(question_index, "")),
                height=150,
                key=f"interview_dashboard_answer_{selected_session_id}_{question_index}",
            )

            if answer_text.strip():
                answers_payload.append(
                    {
                        "question_id": question.get("question_id"),
                        "question_index": question_index,
                        "answer_text": answer_text.strip(),
                    }
                )

        submitted = st.form_submit_button(
            "Сохранить ответы и пересчитать готовность",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not answers_payload:
            st.error("Нужно заполнить хотя бы один ответ.")
            return

        try:
            updated_session = client.patch_json(f"/interviews/sessions/{selected_session_id}/answers",
                {
                    "answers": answers_payload,
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

        if not isinstance(updated_session, dict):
            st.error("Backend вернул неожиданный формат interview session")
            st.json(updated_session)
            return

        selected_session = updated_session
        score = selected_session.get("score") or {}
        feedback = selected_session.get("feedback") or {}

        st.success("Ответы сохранены, готовность пересчитана")

    if score:
        st.markdown("### Текущая оценка готовности")

        question_count = int(score.get("question_count") or len(question_set) or 0)
        answered_score_count = int(score.get("answered_count") or 0)
        unanswered_count = int(score.get("unanswered_count") or 0)
        warning_count = int(score.get("warning_count") or 0)
        readiness_score = score.get("readiness_score")

        col_answered, col_unanswered, col_warnings, col_readiness = st.columns(4)

        with col_answered:
            st.metric("Ответов", f"{answered_score_count} / {question_count}")

        with col_unanswered:
            st.metric("Осталось", unanswered_count)

        with col_warnings:
            st.metric("Предупреждений", warning_count)

        with col_readiness:
            st.metric(
                "Готовность",
                f"{readiness_score} / 100" if readiness_score is not None else "—",
            )

        if question_count > 0:
            st.progress(max(0.0, min(1.0, answered_score_count / question_count)))

        competency_readiness = score.get("competency_readiness") or []

        if competency_readiness:
            st.markdown("### Готовность по компетенциям")

            for competency in competency_readiness:
                competency_name = (
                    competency.get("competency_name")
                    or competency.get("competency_key")
                    or "Компетенция"
                )

                readiness = competency.get("readiness_score")
                answered = competency.get("answered_count", 0)
                total = competency.get("question_count", 0)
                warnings = competency.get("warning_count", 0)

                with st.container(border=True):
                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        st.markdown(f"**{competency_name}**")

                    with col_b:
                        st.metric(
                            "Готовность",
                            f"{readiness} / 100"
                            if readiness is not None
                            else "—",
                        )

                    with col_c:
                        st.metric(
                            "Ответов",
                            f"{answered} / {total}",
                        )

                    if warnings > 0:
                        st.warning(
                            f"Есть предупреждения по ответам: {warnings}"
                        )
                    elif total > 0 and answered == total:
                        st.success("Компетенция полностью покрыта ответами")

            weak_competencies = [
                item
                for item in competency_readiness
                if (item.get("readiness_score") or 100) < 75
            ]

            if weak_competencies:
                st.markdown("### Улучшение слабых зон")

                weak_competency_keys = [
                    item.get("competency_key")
                    for item in weak_competencies
                    if item.get("competency_key")
                ]

                if not weak_competency_keys:
                    st.warning("Backend не вернул ключи weak competencies.")
                else:
                    selected_competency_key = st.selectbox(
                        "Выберите competency для улучшения",
                        options=weak_competency_keys,
                        format_func=lambda key: next(
                            (
                                item.get("competency_name")
                                or item.get("competency_key")
                                for item in weak_competencies
                                if item.get("competency_key") == key
                            ),
                            key,
                        ),
                    )

                    try:
                        competency_detail = client.get_json(
                            (
                                f"/interviews/sessions/{selected_session_id}"
                                f"/competencies/{selected_competency_key}"
                            ),
                            token=token,
                        )
                    except httpx.HTTPStatusError as exc:
                        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
                        st.code(exc.response.text)
                        competency_detail = None
                    except httpx.RequestError as exc:
                        st.error("Не удалось подключиться к backend")
                        st.code(str(exc))
                        competency_detail = None
                    except ValueError as exc:
                        st.error("Backend вернул неожиданный ответ")
                        st.code(str(exc))
                        competency_detail = None

                    if competency_detail is not None:
                        if not isinstance(competency_detail, dict):
                            st.error("Backend вернул неожиданный формат competency detail")
                            st.json(competency_detail)
                        else:
                            questions = competency_detail.get("questions") or []
                            detail_answers = competency_detail.get("answers") or []
                            feedback_items = competency_detail.get("feedback_items") or []
                            attempts = competency_detail.get("attempts") or []

                            answers_by_question_id = {
                                item.get("question_id"): item
                                for item in detail_answers
                            }
                            feedback_by_question_id = {
                                item.get("question_id"): item
                                for item in feedback_items
                            }
                            attempts_by_question_id: dict[str, list[dict]] = {}
                            for attempt in attempts:
                                question_id = attempt.get("question_id")
                                if not question_id:
                                    continue
                                attempts_by_question_id.setdefault(question_id, []).append(attempt)

                            if not questions:
                                st.info("Для этой competency нет связанных вопросов.")

                            for question in questions:
                                question_id = question.get("question_id")
                                prompt = (
                                    question.get("prompt")
                                    or question.get("question_text")
                                    or "Вопрос"
                                )
                                current_answer = (
                                    answers_by_question_id.get(question_id, {}).get("answer_text")
                                    or ""
                                )
                                question_feedback = feedback_by_question_id.get(question_id, {})
                                warnings = question_feedback.get("warnings") or []
                                suggestions = question_feedback.get("suggestions") or []
                                question_attempts = attempts_by_question_id.get(question_id, [])

                                with st.container(border=True):
                                    st.markdown(f"**{localize_demo_ui_text(prompt)}**")

                                    if current_answer:
                                        st.caption("Текущий ответ")
                                        st.write(localize_demo_ui_text(current_answer))
                                    else:
                                        st.warning("Текущий ответ пока не заполнен")

                                    if warnings:
                                        st.warning("Предупреждения: " + ", ".join(warnings))
                                    else:
                                        st.success("Критичных предупреждений нет")

                                    if suggestions:
                                        st.markdown("Рекомендации:")
                                        for suggestion in suggestions:
                                            st.markdown(f"- {suggestion}")

                                    st.caption(f"Попыток улучшения: {len(question_attempts)}")

                                    if not question_id:
                                        st.warning("Backend не вернул question_id для этого вопроса.")
                                        continue

                                    advisory_state_key = (
                                        "ai_advisory_"
                                        f"{selected_session_id}_{question_id}"
                                    )
                                    advisory_error_key = (
                                        "ai_advisory_error_"
                                        f"{selected_session_id}_{question_id}"
                                    )

                                    with st.form(f"ai_advisory_{question_id}"):
                                        submitted_advisory = st.form_submit_button(
                                            "Получить AI-подсказку",
                                            use_container_width=True,
                                            disabled=not current_answer.strip(),
                                        )

                                    if submitted_advisory:
                                        st.session_state.pop(advisory_error_key, None)

                                        if not current_answer.strip():
                                            st.session_state[advisory_error_key] = (
                                                "Сначала нужен текущий ответ, чтобы получить AI-подсказку."
                                            )
                                        else:
                                            try:
                                                with st.spinner("Готовим AI-подсказку..."):
                                                    advisory_result = client.post_json(
                                                        f"/interviews/sessions/{selected_session_id}/coach/advisory",
                                                        {
                                                            "question_id": question_id,
                                                            "answer_text": current_answer.strip(),
                                                            "competency_key": question.get(
                                                                "competency_key"
                                                            ),
                                                        },
                                                        token=token,
                                                    )
                                            except httpx.HTTPStatusError as exc:
                                                st.session_state[advisory_error_key] = (
                                                    "AI advisory вернул ошибку HTTP "
                                                    f"{exc.response.status_code}"
                                                )
                                            except httpx.RequestError as exc:
                                                st.session_state[advisory_error_key] = (
                                                    f"Не удалось получить AI-подсказку: {exc}"
                                                )
                                            except ValueError as exc:
                                                st.session_state[advisory_error_key] = (
                                                    "Backend вернул неожиданный advisory response: "
                                                    f"{exc}"
                                                )
                                            else:
                                                if not isinstance(advisory_result, dict):
                                                    st.session_state[advisory_error_key] = (
                                                        "Backend вернул неожиданный формат advisory response"
                                                    )
                                                else:
                                                    st.session_state[advisory_state_key] = advisory_result
                                                    st.session_state.pop(advisory_error_key, None)

                                        st.rerun()

                                    advisory_error = st.session_state.get(advisory_error_key)
                                    if advisory_error:
                                        st.error(str(advisory_error))

                                    advisory_result = st.session_state.get(advisory_state_key)
                                    if isinstance(advisory_result, dict):
                                        st.markdown("#### AI-подсказка")
                                        st.caption("AI-подсказка не сохраняется автоматически")

                                        strong_parts = advisory_result.get("strong_parts") or []
                                        missing_signals = (
                                            advisory_result.get("missing_signals") or []
                                        )
                                        star_improvements = (
                                            advisory_result.get("star_improvements") or []
                                        )
                                        specificity_gaps = (
                                            advisory_result.get("specificity_gaps") or []
                                        )
                                        risk_warnings = advisory_result.get("risk_warnings") or []
                                        confirmation_needed = (
                                            advisory_result.get("confirmation_needed") or []
                                        )
                                        suggested_revision = (
                                            advisory_result.get("suggested_revision") or ""
                                        )

                                        if strong_parts:
                                            st.markdown("Сильные стороны:")
                                            for item in strong_parts:
                                                st.markdown(f"- {item}")

                                        if missing_signals:
                                            st.markdown("Чего не хватает:")
                                            for item in missing_signals:
                                                st.markdown(f"- {item}")

                                        if star_improvements:
                                            st.markdown("Как усилить по STAR:")
                                            for item in star_improvements:
                                                st.markdown(f"- {item}")

                                        if specificity_gaps:
                                            st.markdown("Где не хватает конкретики:")
                                            for item in specificity_gaps:
                                                st.markdown(f"- {item}")

                                        if risk_warnings:
                                            st.markdown("Риски:")
                                            for item in risk_warnings:
                                                st.markdown(f"- {item}")

                                        if confirmation_needed:
                                            st.markdown("Нужно подтвердить:")
                                            for item in confirmation_needed:
                                                st.markdown(f"- {item}")

                                        if suggested_revision:
                                            st.markdown("Предлагаемая версия:")
                                            st.text_area(
                                                "Suggested revision",
                                                value=localize_demo_ui_text(suggested_revision),
                                                height=180,
                                                disabled=True,
                                                key=(
                                                    "interview_competency_suggested_revision_"
                                                    f"{selected_session_id}_{question_id}"
                                                ),
                                            )

                                    with st.form(f"improve_attempt_{question_id}"):
                                        improved_answer = st.text_area(
                                            "Улучшенный ответ",
                                            value=current_answer,
                                            height=180,
                                            key=(
                                                "interview_competency_attempt_"
                                                f"{selected_session_id}_{question_id}"
                                            ),
                                        )
                                        update_session_answer = st.checkbox(
                                            "Обновить основной ответ в сессии",
                                            value=True,
                                            key=(
                                                "interview_competency_update_session_answer_"
                                                f"{selected_session_id}_{question_id}"
                                            ),
                                        )
                                        submitted_attempt = st.form_submit_button(
                                            "Сохранить improved attempt",
                                            type="primary",
                                            use_container_width=True,
                                        )

                                    if submitted_attempt:
                                        if not improved_answer.strip():
                                            st.error("Нужно заполнить улучшенный ответ.")
                                            return

                                        try:
                                            updated_session = client.post_json(
                                                (
                                                    f"/interviews/sessions/{selected_session_id}"
                                                    f"/questions/{question_id}/attempts"
                                                ),
                                                {
                                                    "answer_text": improved_answer.strip(),
                                                    "update_session_answer": update_session_answer,
                                                },
                                                token=token,
                                            )
                                        except httpx.HTTPStatusError as exc:
                                            st.error(
                                                f"Backend вернул ошибку HTTP {exc.response.status_code}"
                                            )
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

                                        if not isinstance(updated_session, dict):
                                            st.error(
                                                "Backend вернул неожиданный формат interview session"
                                            )
                                            st.json(updated_session)
                                            return

                                        selected_session = updated_session
                                        score = selected_session.get("score") or {}
                                        feedback = selected_session.get("feedback") or {}
                                        new_readiness = score.get("readiness_score")
                                        saved_message = (
                                            "Improved attempt сохранён. Readiness пересчитан."
                                        )
                                        if new_readiness is not None:
                                            saved_message = f"{saved_message} {new_readiness} / 100"
                                        st.session_state[
                                            "interview_competency_attempt_saved_message"
                                        ] = saved_message
                                        st.rerun()

    feedback_items = feedback.get("items") or []
    if feedback_items:
        st.markdown("### Обратная связь")

        for item in feedback_items:
            with st.container(border=True):
                st.markdown(
                    f"**Вопрос {int(item.get('question_index', 0)) + 1} — "
                    f"{format_question_type(item.get('question_type'))}**"
                )
                st.caption(f"Длина ответа: {item.get('answer_length')} символов")

                warnings = item.get("warnings") or []
                suggestions = item.get("suggestions") or []

                if warnings:
                    st.warning("Предупреждения: " + ", ".join(warnings))
                else:
                    st.success("Критичных предупреждений нет")

                if suggestions:
                    st.markdown("Рекомендации:")
                    for suggestion in suggestions:
                        st.markdown(f"- {suggestion}")

    with st.expander("Raw JSON сессии", expanded=False):
        st.json(selected_session)


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

    render_application_dashboard_step(client, token=token)

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

    tab_home, tab_flow, tab_applications, tab_interviews = st.tabs(
        ["Главная", "MVP-сценарий", "Отклики", "Интервью"]
    )

    with tab_home:
        render_home()

    with tab_flow:
        render_mvp_flow(client, token=token)

    with tab_applications:
        render_application_dashboard(client, token=token)

    with tab_interviews:
        render_interview_dashboard(client, token=token)


if __name__ == "__main__":
    main()
