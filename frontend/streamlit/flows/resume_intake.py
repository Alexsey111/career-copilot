# frontend\streamlit\flows\resume_intake.py

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient
from ui.state import (
    _reset_downstream_resume_state,
    _split_csv,
    _store_intake_result_as_resume_import,
)


def _restore_resume_pipeline_state(client: CareerCopilotApiClient, token: str | None) -> bool:
    try:
        state = client.get_resume_pipeline_state(token=token)
    except Exception:
        return False

    if not isinstance(state, dict):
        return False

    restored = False
    for key in ("resume_import", "structured_profile", "achievements"):
        value = state.get(key)
        if isinstance(value, dict) and value:
            st.session_state[key] = value
            restored = True

    return restored


def render_resume_upload_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("1. Источник резюме / профиля")

    active_resume = None
    try:
        active_resume = client.get_active_resume_source(token=token)
    except httpx.HTTPStatusError:
        active_resume = None
    except httpx.RequestError:
        active_resume = None
    except ValueError:
        active_resume = None

    if active_resume:
        st.success("У вас уже есть активное резюме.")
        col_name, col_status, col_updated = st.columns(3)
        col_name.metric("Файл", active_resume.get("original_name") or "Resume")
        col_status.metric("Статус", active_resume.get("lifecycle_status") or "active")
        col_updated.metric("Обновлено", str(active_resume.get("updated_at") or "—")[:10])
        with st.expander("Технические детали активного резюме", expanded=False):
            st.json(
                {
                    "source_file_id": active_resume.get("id"),
                    "content_sha256": active_resume.get("content_sha256"),
                    "lineage_group_id": active_resume.get("lineage_group_id"),
                }
            )
    else:
        st.warning(
            "Активное резюме пока не найдено. Можно загрузить файл, создать профиль вручную "
            "или импортировать публичный GitHub-профиль."
        )

    github_notice = st.session_state.get("github_enrichment_notice")
    if isinstance(github_notice, dict):
        st.success(github_notice.get("message") or "GitHub evidence добавлен к текущему профилю")
        st.json(
            {
                "source": github_notice.get("source"),
                "project_count": github_notice.get("project_count"),
                "evidence_snippet_count": github_notice.get("evidence_snippet_count"),
            }
        )

    options = []
    if active_resume:
        options.append("Использовать текущее")
    options.extend(["Загрузить новое", "Создать вручную", "Импортировать GitHub"])
    if st.session_state.resume_source_mode not in options:
        st.session_state.resume_source_mode = options[0]

    mode = st.radio(
        "Как продолжить?",
        options,
        key="resume_source_mode",
        horizontal=True,
    )

    if mode == "Использовать текущее":
        st.info(
            "Будет использовано уже загруженное активное резюме. "
            "Повторная загрузка файла не нужна."
        )

        if st.button("Использовать текущее резюме и продолжить", type="primary", use_container_width=True):
            st.session_state.source_file = active_resume
            restored = _restore_resume_pipeline_state(client, token)
            if not restored and not st.session_state.get("resume_import"):
                _reset_downstream_resume_state()
            st.session_state["reuse_existing_resume"] = True
            if restored and st.session_state.get("achievements"):
                st.success("Активное резюме выбрано. Готовое состояние восстановлено, можно переходить к вакансии.")
            else:
                st.success(
                    "Активное резюме выбрано. Если импорт уже был выполнен ранее, "
                    "шаги анализа можно пропустить и перейти к вакансии."
                )
            st.rerun()
        return

    if mode == "Создать вручную":
        render_manual_profile_intake_step(client, token=token)
        return

    if mode == "Импортировать GitHub":
        render_github_public_intake_step(client, token=token)
        return

    st.markdown("### Загрузить новое резюме")

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
        st.session_state["reuse_existing_resume"] = False
        st.session_state.pop("github_enrichment_notice", None)
        _reset_downstream_resume_state()
        if result.get("lifecycle_status") == "active" and result.get("content_sha256"):
            st.success("Резюме выбрано. Если такой файл уже был загружен, backend переиспользовал существующий SourceFile.")
        else:
            st.success("Резюме загружено")

    if st.session_state.source_file:
        source_file = st.session_state.source_file

        st.markdown("### Загруженный файл")
        st.json(
            {
                "source_file_id": source_file.get("id"),
                "file_kind": source_file.get("file_kind"),
                "original_name": source_file.get("original_name"),
                "lifecycle_status": source_file.get("lifecycle_status"),
            }
        )


def render_manual_profile_intake_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.markdown("### Создать профиль вручную")
    st.caption("Минимальный intake: raw input сразу сохраняется, структурируется и попадает в evidence bank.")

    with st.form("manual_profile_intake_form"):
        name = st.text_input("Имя")
        location = st.text_input("Локация")
        target_role = st.text_input("Целевая роль", placeholder="AI Automation Specialist")

        technologies = st.text_input("Технологии", placeholder="Python, SQL, FastAPI")
        ai_tools = st.text_input("AI tools", placeholder="ChatGPT, OpenAI, LangChain")
        automation_tools = st.text_input("Automation tools", placeholder="Make, Zapier, n8n")

        st.markdown("#### Опыт / проектная работа")
        exp_name = st.text_input("Компания или проект", placeholder="AI quality workflow")
        exp_role = st.text_input("Роль", placeholder="Automation builder")
        exp_action = st.text_area("Что вы делали", height=90)
        exp_tech = st.text_input("Технологии в опыте", placeholder="Python, ChatGPT")
        exp_result = st.text_input("Результат", placeholder="Сократил ручную проверку на 40%")

        st.markdown("#### Проект")
        project_title = st.text_input("Название проекта", placeholder="Prompt Engineering Toolkit")
        project_description = st.text_area("Описание проекта", height=90)
        project_stack = st.text_input("Стек проекта", placeholder="ChatGPT, Python")
        project_result = st.text_input("Результат проекта")

        submitted = st.form_submit_button(
            "Создать профиль",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    if not target_role.strip() and not exp_action.strip() and not project_description.strip():
        st.error("Заполните хотя бы целевую роль и один опыт или проект.")
        return

    payload: dict[str, Any] = {
        "personal": {
            "name": name.strip() or None,
            "location": location.strip() or None,
            "target_role": target_role.strip() or None,
        },
        "skills": {
            "technologies": _split_csv(technologies),
            "ai_tools": _split_csv(ai_tools),
            "automation_tools": _split_csv(automation_tools),
        },
        "experience": [],
        "projects": [],
        "education": [],
    }
    if exp_name.strip() and exp_action.strip():
        payload["experience"].append(
            {
                "company_or_project": exp_name.strip(),
                "role": exp_role.strip() or None,
                "what_did_you_do": exp_action.strip(),
                "technologies": _split_csv(exp_tech),
                "results": exp_result.strip() or None,
            }
        )
    if project_title.strip() and project_description.strip():
        payload["projects"].append(
            {
                "title": project_title.strip(),
                "description": project_description.strip(),
                "stack": _split_csv(project_stack),
                "results": project_result.strip() or None,
            }
        )

    try:
        result = client.intake_manual_profile(payload, token=token)
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

    st.session_state.source_file = {
        "id": result.get("source_file_id"),
        "file_kind": "manual_profile",
        "original_name": "manual-profile-intake.json",
    }
    st.session_state.pop("github_enrichment_notice", None)
    _reset_downstream_resume_state()
    _store_intake_result_as_resume_import(result)
    st.success("Профиль создан вручную и evidence bank обновлён. Можно продолжать со структурированного профиля.")


def render_github_public_intake_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.markdown("### Импортировать публичный GitHub")
    st.caption(
        "GitHub дополняет текущий профиль и evidence bank проектными сигналами. "
        "Claims не подтверждаются автоматически."
    )

    current_source_file = st.session_state.get("source_file")
    has_resume_context = bool(
        st.session_state.get("resume_import")
        or (
            isinstance(current_source_file, dict)
            and current_source_file.get("file_kind") == "resume"
        )
    )
    if has_resume_context:
        st.info(
            "Будет дополнен текущий профиль. Загруженное резюме останется основным источником, "
            "а GitHub добавит project evidence для генерации документов."
        )

    github_url = st.text_input("GitHub profile URL", placeholder="https://github.com/username")
    target_role = st.text_input("Целевая роль для контекста", placeholder="Python Automation Developer")
    max_repositories = st.slider("Сколько репозиториев импортировать", min_value=1, max_value=30, value=12)
    include_readme = st.checkbox("Читать README snippets", value=True)

    if not st.button("Импортировать GitHub", type="primary", use_container_width=True):
        return

    if not github_url.strip():
        st.error("Укажите GitHub profile URL.")
        return

    try:
        result = client.import_github_public_profile(
            profile_url=github_url.strip(),
            target_role=target_role.strip() or None,
            max_repositories=max_repositories,
            include_readme=include_readme,
            token=token,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 502:
            st.warning(
                "GitHub API сейчас недоступен для backend. "
                "Проверьте DNS/интернет у backend-контейнера или повторите импорт позже."
            )
            st.code(exc.response.text)
            return
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.TimeoutException as exc:
        st.error(
            "GitHub import не успел завершиться. "
            "Попробуйте уменьшить количество репозиториев или отключить README snippets."
        )
        st.code(str(exc))
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend.")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ")
        st.code(str(exc))
        return

    if has_resume_context:
        _restore_resume_pipeline_state(client, token)
        st.session_state["github_enrichment_notice"] = {
            "message": "GitHub evidence добавлен к текущему профилю",
            "project_count": result.get("project_count"),
            "evidence_snippet_count": result.get("evidence_snippet_count"),
            "source": result.get("source"),
        }
        st.success(
            "GitHub evidence добавлен к текущему профилю. "
            "Резюме остаётся активным источником, можно продолжать к вакансии."
        )
        st.rerun()
        return

    st.session_state.source_file = {
        "id": result.get("source_file_id"),
        "file_kind": "github_public_profile",
        "original_name": "github-public-profile-intake.json",
    }
    st.session_state.pop("github_enrichment_notice", None)
    _reset_downstream_resume_state()
    _store_intake_result_as_resume_import(result)
    st.success("GitHub evidence импортирован. Факты помечены как needs_confirmation.")


def render_resume_import_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("2. Импорт резюме")

    source_file = st.session_state.source_file
    if not source_file:
        st.info("Сначала загрузите файл резюме на шаге 1.")
        return

    if st.session_state.resume_import and source_file.get("file_kind") != "resume":
        st.success("Профиль уже создан через guided intake. Импорт файла резюме не требуется.")
        resume_import = st.session_state.resume_import
        st.json(
            {
                "profile_id": resume_import.get("profile_id"),
                "source_file_id": resume_import.get("source_file_id"),
                "extraction_id": resume_import.get("extraction_id"),
                "source": resume_import.get("detected_format"),
            }
        )
        return

    source_file_id = source_file.get("id")
    if not source_file_id:
        st.error("В загруженном файле не найден source_file_id.")
        st.json(source_file)
        return

    st.caption(f"source_file_id: {source_file_id}")

    if st.session_state.get("reuse_existing_resume") and st.session_state.resume_import:
        st.success("Импорт активного резюме уже готов. Повторный импорт не нужен.")
        resume_import = st.session_state.resume_import
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
        return

    if st.session_state.get("reuse_existing_resume") and not st.session_state.resume_import:
        st.info(
            "Используется активное резюме. Backend проверит существующий extraction "
            "и не будет повторно парсить файл, если extraction уже есть."
        )

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

    if st.session_state.get("reuse_existing_resume") and st.session_state.structured_profile:
        st.success("Структурированный профиль уже готов. Повторное извлечение не нужно.")
        profile = st.session_state.structured_profile
        st.json(
            {
                "profile_id": profile.get("profile_id"),
                "extraction_id": profile.get("extraction_id"),
                "full_name": profile.get("full_name"),
                "headline": profile.get("headline"),
                "experience_count": profile.get("experience_count", 0),
            }
        )
        return

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
        warning_labels = {
            "contacts, achievements, metrics and proof-status mapping are not extracted in v1": (
                "В этой версии контакты, метрики и подтверждения фактов извлекаются частично. "
                "Проверьте достижения на следующем шаге."
            ),
        }

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
                st.warning(warning_labels.get(str(warning), str(warning)))

        with st.expander("Технический JSON результата", expanded=False):
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

    achievements_already_ready = (
        st.session_state.get("reuse_existing_resume")
        and st.session_state.achievements
    )
    if achievements_already_ready:
        st.success("Достижения уже извлечены. Повторный анализ не нужен.")

    if not achievements_already_ready and st.button("Извлечь достижения", type="primary", use_container_width=True):
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

    st.markdown("#### GitHub project drafts")

    if st.button(
        "Сгенерировать черновики проектов из GitHub evidence",
        use_container_width=True,
    ):
        try:
            result = client.generate_repository_achievements(token=token)
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
        st.success(
            "Черновики проектов из GitHub evidence добавлены. "
            "Проверьте и подтвердите их ниже."
        )
        st.rerun()

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

        with st.expander("Технический JSON результата", expanded=False):
            st.json(achievements_result)


