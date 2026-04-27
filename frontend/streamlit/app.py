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
        st.session_state.achievements = None
        st.session_state.vacancy_analysis = None
        st.session_state.generated_resume = None
        st.session_state.generated_cover_letter = None
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
                    else:
                        st.caption(f"fact_status: {fact_status}")

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

    steps = [
        "9. Подтвердить документы",
        "10. Создать отклик",
        "11. Создать подготовку к интервью",
    ]

    st.subheader("Следующие шаги")
    for step in steps:
        st.checkbox(step, value=False, disabled=True)

    st.warning("Следующие действия будут подключаться по одному в Priority 10.10+.")


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
