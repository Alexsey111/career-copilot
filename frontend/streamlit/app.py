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
    "submitted": "Отправлен вручную",
    "interview": "Интервью",
    "rejected": "Отказ",
    "offer": "Оффер",
}


def format_application_status(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_STATUS_LABELS.get(value, value)


def format_optional_datetime(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ")[:19]


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
        "Frontend подключает полный MVP-сценарий. "
        "Все внешние действия остаются human-in-the-loop: система не отправляет отклики автоматически."
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


def render_achievements_step(client: CareerCopilotApiClient) -> None:
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
            result = client.post_json(
                "/profile/extract-achievements",
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
                        result = client.patch_json(
                            f"/profile/achievements/{item['id']}/review",
                            {
                                "title": str(item["title"]).strip(),
                                "fact_status": item["fact_status"],
                                "evidence_note": str(item.get("evidence_note") or "").strip()
                                or None,
                            },
                        )

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


def render_vacancy_import_step(client: CareerCopilotApiClient) -> None:
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
            value="Backend Developer",
        )
        company = st.text_input(
            "Компания",
            value="Test Company",
        )
        location = st.text_input(
            "Локация",
            value="Remote",
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
            result = client.post_json(
                "/vacancies/import",
                payload,
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


def render_vacancy_analysis_step(client: CareerCopilotApiClient) -> None:
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
            result = client.post_json(
                f"/vacancies/{vacancy_id}/analyze",
                {},
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


def render_resume_generation_step(client: CareerCopilotApiClient) -> None:
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
            result = client.post_json(
                "/documents/resumes/generate",
                {
                    "vacancy_id": vacancy_id,
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


def render_cover_letter_generation_step(client: CareerCopilotApiClient) -> None:
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
            result = client.post_json(
                "/documents/letters/generate",
                {
                    "vacancy_id": vacancy_id,
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

        review_status = letter.get("review_status")
        if review_status == "draft":
            st.info("Статус документа: draft. Следующий шаг — проверка и подтверждение.")


def render_document_approval_step(client: CareerCopilotApiClient) -> None:
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
            approved_resume = client.patch_json(
                f"/documents/{resume_document_id}/review",
                {
                    "review_status": "approved",
                    "review_comment": review_comment.strip() or None,
                    "set_active_when_approved": True,
                },
            )

            approved_cover_letter = client.patch_json(
                f"/documents/{cover_letter_document_id}/review",
                {
                    "review_status": "approved",
                    "review_comment": review_comment.strip() or None,
                    "set_active_when_approved": True,
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
                resume_txt = client.get_text(f"/documents/{approved_resume_id}/export/txt")
                resume_md = client.get_text(f"/documents/{approved_resume_id}/export/md")
                cover_letter_txt = client.get_text(
                    f"/documents/{approved_cover_letter_id}/export/txt"
                )
                cover_letter_md = client.get_text(
                    f"/documents/{approved_cover_letter_id}/export/md"
                )
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


def render_application_creation_step(client: CareerCopilotApiClient) -> None:
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
            result = client.post_json(
                "/applications",
                {
                    "vacancy_id": vacancy_id,
                    "resume_document_id": resume_document_id,
                    "cover_letter_document_id": cover_letter_document_id,
                    "notes": notes.strip() or None,
                },
            )
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
                "channel": application.get("channel"),
                "applied_at": application.get("applied_at"),
                "notes": application.get("notes"),
                "created_at": application.get("created_at"),
            }
        )

        if application.get("status") == "draft":
            st.info(
                "Отклик создан в статусе draft. Это не означает отправку. "
                "После ручной отправки на HH статус можно будет изменить на submitted отдельным шагом."
            )


def render_application_status_update_step(client: CareerCopilotApiClient) -> None:
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

    if current_status == "submitted":
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

    st.warning(
        "Нажимайте эту кнопку только после того, как вы вручную отправили отклик на HH "
        "или другой площадке. Система сама ничего не отправляет."
    )

    notes = st.text_area(
        "Заметка после ручной отправки",
        value="Отклик отправлен вручную на HH.",
        height=90,
    )

    if st.button(
        "Отметить как отправленный вручную",
        type="primary",
        use_container_width=True,
    ):
        try:
            result = client.patch_json(
                f"/applications/{application_id}/status",
                {
                    "status": "submitted",
                    "notes": notes.strip() or None,
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


def render_application_dashboard_step(client: CareerCopilotApiClient) -> None:
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
            result = client.get_json("/applications")
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

    col_total, col_draft, col_submitted, col_interview, col_final = st.columns(5)

    with col_total:
        st.metric("Всего", len(applications))

    with col_draft:
        st.metric("Черновики", status_counts.get("draft", 0))

    with col_submitted:
        st.metric("Отправлены", status_counts.get("submitted", 0))

    with col_interview:
        st.metric("Интервью", status_counts.get("interview", 0))

    with col_final:
        st.metric(
            "Финальные",
            status_counts.get("rejected", 0) + status_counts.get("offer", 0),
        )

    rows = []
    for item in applications:
        rows.append(
            {
                "Вакансия": item.get("vacancy_title") or "—",
                "Компания": item.get("vacancy_company") or "—",
                "Локация": item.get("vacancy_location") or "—",
                "Статус": format_application_status(item.get("status")),
                "Канал": item.get("channel") or "—",
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
                    "channel": item.get("channel"),
                    "applied_at": item.get("applied_at"),
                    "outcome": item.get("outcome"),
                    "notes": item.get("notes"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )


def render_interview_preparation_step(client: CareerCopilotApiClient) -> None:
    st.subheader("13. Подготовка к собеседованию")

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    if application.get("status") != "submitted":
        st.info(
            "Подготовку к интервью лучше создавать после того, как отклик вручную отправлен "
            "и отмечен как submitted на шаге 11."
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
            result = client.post_json(
                "/interviews/sessions",
                {
                    "vacancy_id": vacancy_id,
                    "session_type": "vacancy",
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
            "question_types": question_types,
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

            st.markdown(f"**{index}. {question_type}**")
            st.write(prompt)
            if answer_format:
                st.caption(f"Формат ответа: {answer_format}")

    st.markdown("### Ответы на вопросы интервью")

    st.info(
        "Можно заполнить часть ответов и сохранить промежуточный результат. "
        "Для STAR-вопросов используйте структуру: Ситуация / Задача / Действия / Результат."
    )

    default_answers = {
        0: (
            "Я рассматриваю эту роль, потому что она связана с backend-разработкой "
            "и позволяет применить мой практический опыт с Python и AI-инструментами."
        ),
        1: (
            "Ситуация: я работал над практическим Python-проектом. "
            "Задача: нужно было собрать рабочий backend-прототип. "
            "Действия: я реализовал основной API-flow и проверил его через smoke-сценарий. "
            "Результат: прототип был готов для дальнейшей проверки и улучшения."
        ),
    }

    with st.form(f"interview_answers_form_{session_id}"):
        answers_payload: list[dict] = []

        for question_index, question in enumerate(question_set):
            question_number = question_index + 1
            question_type = question.get("type") or "unknown"
            prompt = question.get("prompt") or f"Вопрос {question_number}"
            answer_format = question.get("answer_format")

            st.markdown(f"#### Вопрос {question_number}: {question_type}")
            st.write(prompt)

            if answer_format:
                st.caption(f"Формат ответа: {answer_format}")

            answer_text = st.text_area(
                f"Ответ {question_number}",
                value=default_answers.get(question_index, ""),
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
            result = client.patch_json(
                f"/interviews/sessions/{session_id}/answers",
                {
                    "answers": answers_payload,
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
            st.metric("Статус", answered.get("status"))

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
                        f"{item.get('question_type')}**"
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


def render_application_dashboard(client: CareerCopilotApiClient) -> None:
    st.header("Дашборд откликов")
    st.caption(
        "Список внутренних записей откликов. Это не отправляет отклики на HH и не выполняет внешних действий."
    )

    status_labels = {
        "draft": "Черновик",
        "submitted": "Отправлен вручную",
        "interview": "Интервью",
        "rejected": "Отказ",
        "offer": "Оффер",
    }

    allowed_next_statuses = {
        "draft": ["submitted"],
        "submitted": ["interview", "rejected", "offer"],
        "interview": ["rejected", "offer"],
        "rejected": [],
        "offer": [],
    }

    try:
        applications = client.get_json("/applications")
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
        "submitted": 0,
        "interview": 0,
        "rejected": 0,
        "offer": 0,
    }

    for application in applications:
        status_value = application.get("status")
        if status_value in counts_by_status:
            counts_by_status[status_value] += 1

    metric_cols = st.columns(5)

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
                "Статус": status_labels.get(status_value, status_value),
                "application_id": application.get("id"),
                "vacancy_id": application.get("vacancy_id"),
                "applied_at": application.get("applied_at"),
                "outcome": application.get("outcome"),
                "created_at": application.get("created_at"),
                "notes": application.get("notes"),
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
        selected_application = client.get_json(f"/applications/{selected_application_id}")
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
            "channel": selected_application.get("channel"),
            "applied_at": selected_application.get("applied_at"),
            "outcome": selected_application.get("outcome"),
            "notes": selected_application.get("notes"),
            "created_at": selected_application.get("created_at"),
            "updated_at": selected_application.get("updated_at"),
        }
    )

    current_status = str(selected_application.get("status") or "").strip().lower()
    next_statuses = allowed_next_statuses.get(current_status, [])

    st.markdown("### Ручное обновление статуса")

    if not next_statuses:
        st.info(
            "Для текущего статуса нет разрешённых следующих переходов. "
            "Финальные статусы не переоткрываются автоматически."
        )
        return

    with st.form(f"application_status_dashboard_form_{selected_application_id}"):
        next_status = st.selectbox(
            "Новый статус",
            options=next_statuses,
            format_func=lambda value: status_labels.get(value, value),
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
            updated_application = client.patch_json(
                f"/applications/{selected_application_id}/status",
                {
                    "status": next_status,
                    "notes": notes.strip() or None,
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

        if not isinstance(updated_application, dict):
            st.error("Backend вернул неожиданный формат отклика")
            st.json(updated_application)
            return

        st.success("Статус отклика обновлён")
        st.rerun()


def render_mvp_flow(client: CareerCopilotApiClient) -> None:
    st.header("MVP-сценарий")

    render_resume_upload_step(client)

    st.divider()

    render_resume_import_step(client)

    st.divider()

    render_structured_profile_step(client)

    st.divider()

    render_achievements_step(client)

    st.divider()

    render_vacancy_import_step(client)

    st.divider()

    render_vacancy_analysis_step(client)

    st.divider()

    render_resume_generation_step(client)

    st.divider()

    render_cover_letter_generation_step(client)

    st.divider()

    render_document_approval_step(client)

    st.divider()

    render_application_creation_step(client)

    st.divider()

    render_application_status_update_step(client)

    st.divider()

    render_application_dashboard_step(client)

    st.divider()

    render_interview_preparation_step(client)

    st.divider()

    st.success(
        "Сквозной MVP-сценарий во frontend подключён: резюме → вакансия → документы → "
        "ручной отклик → подготовка к интервью."
    )


def main() -> None:
    init_session_state()
    _, client = render_sidebar()

    tab_home, tab_flow, tab_applications = st.tabs(
        ["Главная", "MVP-сценарий", "Отклики"]
    )

    with tab_home:
        render_home()

    with tab_flow:
        render_mvp_flow(client)

    with tab_applications:
        render_application_dashboard(client)


if __name__ == "__main__":
    main()
