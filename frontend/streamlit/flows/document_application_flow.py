# frontend\streamlit\flows\document_application_flow.py

from __future__ import annotations

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient
from components import (
    render_document_review_workspace_tab,
    render_interview_prep_workspace_tab,
)
from components.document_review_workspace import _render_export_controls
from ui.navigation import navigate_to_mvp_step
from ui.formatting import format_application_status
from ui.formatting import format_optional_datetime


def _humanize_application_status(value: object) -> str:
    status = str(value or "").strip().lower()
    labels = {
        "draft": "черновик",
        "ready": "готов к ручной отправке",
        "applied": "отправлен",
        "review_required": "требует проверки",
        "rejected": "отклонён",
        "archived": "архив",
    }
    return labels.get(status, status or "—")


def _humanize_review_status(value: object) -> str:
    status = str(value or "").strip().lower()
    labels = {
        "draft": "черновик",
        "review_required": "требует проверки",
        "reviewed": "проверен",
        "approved": "утверждён",
        "archived": "архив",
    }
    return labels.get(status, status or "—")


def _humanize_status_history_value(value: object) -> str:
    status = str(value or "").strip().lower()
    if not status or status == "none":
        return "не указан"
    return format_application_status(status)


def _humanize_status_history_timestamp(value: object) -> str:
    formatted = format_optional_datetime(str(value or "").strip() or None)
    return formatted if formatted != "—" else "не указана"


def _format_status_history_entry(item: dict[str, object]) -> str:
    created_at = _humanize_status_history_timestamp(item.get("created_at"))
    previous_status = _humanize_status_history_value(item.get("previous_status"))
    new_status = _humanize_status_history_value(item.get("new_status"))

    transition = f"{previous_status} → {new_status}"
    if created_at != "не указана":
        return f"{created_at}: {transition}"
    return transition


def _render_application_tracking_inline(
    client: CareerCopilotApiClient,
    *,
    application_id: str,
    token: str | None,
) -> None:
    st.markdown("### История статусов")

    try:
        timeline = client.get_json(f"/applications/{application_id}/timeline", token=token)
    except Exception as exc:
        st.caption(f"История статусов пока недоступна: {exc}")
        return

    if isinstance(timeline, list) and timeline:
        for item in timeline:
            if isinstance(item, dict):
                st.markdown(f"- {_format_status_history_entry(item)}")
        return

    st.caption("История статусов пока недоступна.")


def _provenance_labels_from_review_summary(summary: dict) -> list[str]:
    labels: list[str] = []
    for item in summary.get("evidence_selection_reason") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("provenance_label") or "").strip()
        if not label:
            category = str(item.get("category") or "").strip()
            title = str(item.get("title") or item.get("item") or "").strip()
            category_labels = {
                "github_architecture": "GitHub architecture evidence",
                "automation_project": "AI workflow orchestration",
                "computer_vision": "Computer vision project",
                "analytics_project": "Analytics project",
                "backend_project": "Backend project",
            }
            label = category_labels.get(category, title)
        if label and label not in labels:
            labels.append(label)

    for item in summary.get("selected_achievements") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        label = f"Resume achievement: {title}" if title else "Resume achievement"
        if label not in labels:
            labels.append(label)

    return labels


def _render_resume_provenance_preview(
    client: CareerCopilotApiClient,
    *,
    document_id: str,
    token: str | None,
) -> None:
    if not client.has_entity_id(document_id):
        st.caption("Информация об использованных доказательствах пока недоступна.")
        return

    try:
        summary = client.get_document_review_details(document_id, token=token)
    except Exception as exc:
        st.caption("Информация об использованных доказательствах пока недоступна.")
        with st.expander("Технические детали", expanded=False):
            st.code(str(exc))
        return

    if not isinstance(summary, dict):
        return

    labels = _provenance_labels_from_review_summary(summary)
    if not labels:
        return

    st.markdown("#### Использовано")
    for label in labels[:6]:
        st.markdown(f"- ✓ {label}")


def render_resume_generation_step(
    client: CareerCopilotApiClient,
    token: str | None = None,
    *,
    show_title: bool = True,
) -> None:
    if show_title:
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

    with st.expander("Технические детали", expanded=False):
        st.caption(f"vacancy_id: {vacancy_id}")
        resume_import = st.session_state.get("resume_import") or {}
        structured_profile = st.session_state.get("structured_profile") or {}
        st.json(
            {
                "resume_extraction_id": resume_import.get("extraction_id"),
                "structured_profile_extraction_id": structured_profile.get("extraction_id"),
                "structured_profile_full_name": structured_profile.get("full_name"),
                "structured_profile_experience_count": structured_profile.get("experience_count"),
                "current_generated_resume_document_id": (
                    st.session_state.generated_resume or {}
                ).get("document_id"),
            }
        )

    resume_import_extraction_id = resume_import.get("extraction_id")
    structured_profile_extraction_id = structured_profile.get("extraction_id")

    if (
        resume_import_extraction_id
        and structured_profile_extraction_id
        and resume_import_extraction_id != structured_profile_extraction_id
    ):
        st.error(
            "Состояние резюме рассинхронизировано: импорт и структурированный профиль "
            "относятся к разным extraction_id. Повторите шаг 3."
        )
        st.json(
            {
                "resume_import_extraction_id": resume_import_extraction_id,
                "structured_profile_extraction_id": structured_profile_extraction_id,
            }
        )
        return

    match_score = vacancy_analysis.get("match_score")
    if match_score is not None:
        st.metric("Совпадение перед генерацией", match_score)

    st.warning(
        "Резюме будет создано как draft. Перед использованием его нужно проверить и подтвердить человеком."
    )

    if st.button("Сгенерировать адаптированное резюме", type="primary", width="stretch"):
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
        navigate_to_mvp_step(8)

    if st.session_state.generated_resume:
        resume = st.session_state.generated_resume

        st.markdown("### Сгенерированное резюме")
        st.caption(f"Статус: {_humanize_review_status(resume.get('review_status'))}")
        if resume.get("version_label"):
            st.caption(f"Версия: {resume.get('version_label')}")
        with st.expander("Технические детали", expanded=False):
            st.json(
                {
                    "document_id": resume.get("document_id"),
                    "vacancy_id": resume.get("vacancy_id"),
                    "review_status": resume.get("review_status"),
                    "version_label": resume.get("version_label"),
                    "created_at": resume.get("created_at"),
                }
            )

        document_id = resume.get("document_id")
        if document_id:
            _render_resume_provenance_preview(
                client,
                document_id=str(document_id),
                token=token,
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
            st.info("Статус документа: черновик. Следующий шаг — проверка и подтверждение.")


def render_cover_letter_generation_step(
    client: CareerCopilotApiClient,
    token: str | None = None,
    *,
    show_title: bool = True,
) -> None:
    if show_title:
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

    with st.expander("Технические детали", expanded=False):
        st.caption(f"vacancy_id: {vacancy_id}")

    match_score = vacancy_analysis.get("match_score")
    if match_score is not None:
        st.metric("Совпадение перед генерацией письма", match_score)

    st.warning(
        "Письмо будет создано как draft. Перед отправкой его нужно проверить и подтвердить человеком."
    )

    if st.button(
        "Сгенерировать сопроводительное письмо",
        type="primary",
        width="stretch",
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
        navigate_to_mvp_step(9)

    if st.session_state.generated_cover_letter:
        letter = st.session_state.generated_cover_letter

        st.markdown("### Сгенерированное сопроводительное письмо")
        st.caption(f"Статус: {_humanize_review_status(letter.get('review_status'))}")
        if letter.get("version_label"):
            st.caption(f"Версия: {letter.get('version_label')}")
        with st.expander("Технические детали", expanded=False):
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
            st.info("Статус документа: черновик. Следующий шаг — проверка и подтверждение.")


def _render_selected_documents_panel(
    client: CareerCopilotApiClient,
    *,
    token: str | None,
) -> None:
    approved_resume = st.session_state.get("approved_resume")
    approved_cover_letter = st.session_state.get("approved_cover_letter")

    if not approved_resume and not approved_cover_letter:
        return

    st.markdown("### Выбранные документы")

    col_resume, col_letter = st.columns(2)

    with col_resume:
        with st.container(border=True):
            st.markdown("#### Резюме")
            if isinstance(approved_resume, dict):
                document_id = str(
                    approved_resume.get("id")
                    or approved_resume.get("document_id")
                    or ""
                ).strip()
                st.success("Выбрано ✅")
                if document_id:
                    _render_export_controls(
                        client,
                        document_id=document_id,
                        document_kind="resume",
                        token=token,
                        key_suffix="step9_selected_resume",
                    )
                else:
                    st.caption("document_id недоступен.")
            else:
                st.caption("Пока не выбрано.")

    with col_letter:
        with st.container(border=True):
            st.markdown("#### Сопроводительное письмо")
            if isinstance(approved_cover_letter, dict):
                document_id = str(
                    approved_cover_letter.get("id")
                    or approved_cover_letter.get("document_id")
                    or ""
                ).strip()
                st.success("Выбрано ✅")
                if document_id:
                    _render_export_controls(
                        client,
                        document_id=document_id,
                        document_kind="cover_letter",
                        token=token,
                        key_suffix="step9_selected_cover_letter",
                    )
                else:
                    st.caption("document_id недоступен.")
            else:
                st.caption("Пока не выбрано.")


def render_document_approval_step(
    client: CareerCopilotApiClient,
    token: str | None = None,
    *,
    show_title: bool = True,
) -> None:
    st.markdown('<div id="step-9-document-review"></div>', unsafe_allow_html=True)
    if show_title:
        st.subheader("9. Проверка и подтверждение документов")

    resume_ready = bool(st.session_state.get("approved_resume"))
    cover_letter_ready = bool(st.session_state.get("approved_cover_letter"))

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Резюме",
            "Готово ✅" if resume_ready else "Не выбрано",
        )

    with col2:
        st.metric(
            "Сопроводительное письмо",
            "Готово ✅" if cover_letter_ready else "Не выбрано",
        )

    _render_selected_documents_panel(client, token=token)

    selection_key = "document_review_workspace_step9_selection"

    if resume_ready and not cover_letter_ready:
        st.session_state[f"{selection_key}_preferred_kind"] = "cover_letter"
        st.session_state.pop(selection_key, None)
        st.session_state.pop(f"{selection_key}_picker", None)

    elif cover_letter_ready and not resume_ready:
        st.session_state[f"{selection_key}_preferred_kind"] = "resume"
        st.session_state.pop(selection_key, None)
        st.session_state.pop(f"{selection_key}_picker", None)

    if resume_ready and not cover_letter_ready:
        st.markdown("### Следующее действие")
        st.info("Резюме выбрано и доступно для скачивания выше. Теперь ниже открыт выбор сопроводительного письма.")
    elif cover_letter_ready and not resume_ready:
        st.markdown("### Следующее действие")
        st.info("Сопроводительное письмо выбрано и доступно для скачивания выше. Теперь ниже открыт выбор резюме.")
    elif not resume_ready and not cover_letter_ready:
        st.markdown("### Следующее действие")
        st.info("Сначала выберите резюме, затем сопроводительное письмо.")
    else:
        st.success("Оба документа выбраны. Можно переходить к шагу 10.")

    st.session_state.pop("document_review_step9_return_notice", None)

    vacancy = st.session_state.vacancy or {}
    current_vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    st.markdown('<div id="step-9-document-picker"></div>', unsafe_allow_html=True)
    render_document_review_workspace_tab(
        client,
        token=token,
        selection_state_key=selection_key,
        current_vacancy_id=str(current_vacancy_id) if current_vacancy_id else None,
        show_only_current_vacancy=True,
    )


def render_application_creation_step(
    client: CareerCopilotApiClient,
    token: str | None = None,
    *,
    show_title: bool = True,
) -> None:
    if show_title:
        st.subheader("10. Сохранить отклик в трекере")

    vacancy = st.session_state.vacancy
    if not vacancy:
        st.info("Сначала импортируйте вакансию на шаге 5.")
        return

    approved_resume = st.session_state.approved_resume
    if not approved_resume:
        st.info("Сначала выберите резюме на шаге 9: утвердите его или используйте как draft.")
        return

    approved_cover_letter = st.session_state.approved_cover_letter
    if not approved_cover_letter:
        st.info(
            "Сначала выберите сопроводительное письмо на шаге 9: "
            "утвердите его или используйте как draft."
        )
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

    resume_is_final = (
        approved_resume.get("review_status") == "approved"
        and bool(approved_resume.get("is_active"))
    )
    cover_letter_is_final = (
        approved_cover_letter.get("review_status") == "approved"
        and bool(approved_cover_letter.get("is_active"))
    )

    if not resume_is_final or not cover_letter_is_final:
        st.warning(
            "Один или оба документа используются как draft. "
            "Отклик будет создан с пометкой review_required."
        )

    with st.expander("Технические детали", expanded=False):
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

    if st.button("Сохранить отклик в трекере", type="primary", width="stretch"):
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
        st.success("Отклик сохранён в трекере")
        navigate_to_mvp_step(11)

        if result.get("review_required"):
            st.warning("Не финализировано / требуется review.")
            blockers = result.get("review_blockers") or []
            warnings = result.get("review_warnings") or []
            if blockers:
                st.markdown("**Блокеры проверки:**")
                for item in blockers:
                    st.markdown(f"- {item}")
            if warnings:
                st.markdown("**Предупреждения проверки:**")
                for item in warnings:
                    st.markdown(f"- {item}")

    if st.session_state.application:
        application = st.session_state.application

        st.markdown("### Отклик в трекере")
        st.caption(f"Статус: {_humanize_application_status(application.get('status'))}")
        if application.get("notes"):
            st.caption(f"Заметка: {application.get('notes')}")
        if application.get("review_required"):
            st.warning("Отклик требует проверки перед отправкой.")
        with st.expander("Технические детали", expanded=False):
            st.json(
                {
                    "application_id": application.get("id"),
                    "vacancy_id": application.get("vacancy_id"),
                    "resume_document_id": application.get("resume_document_id"),
                    "cover_letter_document_id": application.get("cover_letter_document_id"),
                    "status": application.get("status"),
                    "source": application.get("source"),
                    "applied_at": application.get("applied_at"),
                    "review_required": application.get("review_required"),
                    "review_blockers": application.get("review_blockers"),
                    "review_warnings": application.get("review_warnings"),
                    "created_at": application.get("created_at"),
                }
            )

        if application.get("status") == "draft":
            st.info(
                "Отклик создан в статусе draft. Это не означает отправку. "
                "После ручной отправки на HH статус можно будет изменить на applied отдельным шагом."
            )


def render_application_status_update_step(
    client: CareerCopilotApiClient,
    token: str | None = None,
    *,
    show_title: bool = True,
) -> None:
    if show_title:
        st.subheader("11. Отправка и отслеживание отклика")

    application = st.session_state.application
    if not application:
        st.info("Сначала сохраните отклик в трекере на шаге 10.")
        return

    application_id = application.get("id")
    if not application_id:
        st.error("В отклике не найден application_id.")
        st.json(application)
        return

    try:
        fresh_application = client.get_json(
            f"/applications/{application_id}",
            token=token,
        )
        if isinstance(fresh_application, dict):
            st.session_state.application = fresh_application
            application = fresh_application
    except Exception:
        pass

    current_status = application.get("status")
    st.caption(f"Текущий статус: {_humanize_application_status(current_status)}")
    st.info(
        "Система не отправляет отклик автоматически. "
        "Сначала подготовьте пакет документов, затем вручную отправьте отклик на HH "
        "или другой площадке и отметьте это здесь."
    )
    with st.expander("Технические детали", expanded=False):
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

    allowed_statuses = {
        str(item.get("status") or "")
        for item in (workflow.get("allowed_transitions") or [])
        if isinstance(item, dict)
    }

    if current_status == "draft" and "ready" in allowed_statuses:
        st.markdown("### 11.1 Подготовить отклик")
        st.caption("Это внутренняя отметка: пакет документов готов к ручной отправке.")
        st.info(
            "Отклик создан как черновик. Перед ручной отправкой пометьте его готовым."
        )

        if st.button(
            "Пометить отклик готовым к ручной отправке",
            type="primary",
            width="stretch",
        ):
            try:
                result = client.patch_json(
                    f"/applications/{application_id}/status",
                    {
                        "status": "ready",
                        "notes": "Marked ready via Streamlit UI.",
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
                st.error("Backend вернул неожиданный формат ответа")
                st.json(result)
                return

            st.session_state.application = result
            st.success("Отклик помечен как готовый к ручной отправке")
            st.rerun()

        return

    if current_status == "applied":
        st.success("Отклик уже отмечен как отправленный.")
        if application.get("applied_at"):
            st.caption(f"Дата отправки: {application.get('applied_at')}")
        if application.get("notes"):
            st.caption(f"Заметка: {application.get('notes')}")
        with st.expander("Технические детали", expanded=False):
            st.json(
                {
                    "application_id": application.get("id"),
                    "status": application.get("status"),
                    "applied_at": application.get("applied_at"),
                }
            )
        return

    if not workflow.get("can_submit"):
        st.info(
            "Ручная отметка отправки недоступна для текущего статуса. "
            "Backend сам определяет, когда submit доступен."
        )
        with st.expander("Метаданные workflow", expanded=False):
            st.json(workflow)
        return

    st.markdown("### 11.2 Подтвердить ручную отправку")
    st.caption("Нажимайте только после того, как реально отправили отклик на HH/другой площадке.")
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
        "Я отправил отклик вручную",
        type="primary",
        width="stretch",
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

        fresh_application = client.get_json(
            f"/applications/{application_id}",
            token=token,
        )
        if isinstance(fresh_application, dict):
            st.session_state.application = fresh_application
        else:
            st.session_state.application = result

        st.toast("Отклик отмечен как отправленный", icon="✅")
        st.rerun()

    if st.session_state.application:
        updated_application = st.session_state.application

        st.markdown("### Текущий статус отклика")
        st.caption(f"Статус: {_humanize_application_status(updated_application.get('status'))}")
        if updated_application.get("applied_at"):
            st.caption(f"Дата отправки: {updated_application.get('applied_at')}")
        if updated_application.get("notes"):
            st.caption(f"Заметка: {updated_application.get('notes')}")
        with st.expander("Технические детали", expanded=False):
            st.json(
                {
                    "application_id": updated_application.get("id"),
                    "vacancy_id": updated_application.get("vacancy_id"),
                    "status": updated_application.get("status"),
                    "applied_at": updated_application.get("applied_at"),
                    "updated_at": updated_application.get("updated_at"),
                }
            )

        st.divider()
        _render_application_tracking_inline(
            client,
            application_id=str(application_id),
            token=token,
        )


def _render_application_tracking_inline(
    client: CareerCopilotApiClient,
    *,
    application_id: str,
    token: str | None,
) -> None:
    st.markdown("### История отклика")

    try:
        timeline = client.get_json(f"/applications/{application_id}/timeline", token=token)
    except Exception as exc:
        st.caption(f"История статусов пока недоступна: {exc}")
        return

    if not isinstance(timeline, list) or not timeline:
        st.caption("История статусов пока пуста.")
        return

    for item in timeline:
        if isinstance(item, dict):
            st.markdown(f"- {_format_status_history_entry(item)}")


def render_application_tracking_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("12. Статус отклика")

    application = st.session_state.application
    if not application:
        st.info("Сначала сохраните отклик в трекере на шаге 10.")
        return

    application_id = application.get("id")
    if not application_id:
        st.error("В отклике не найден application_id.")
        st.json(application)
        return

    st.caption(f"Статус: {_humanize_application_status(application.get('status'))}")
    if application.get("review_required"):
        st.warning("Отклик требует проверки.")
    with st.expander("Технические детали", expanded=False):
        st.caption(f"application_id: {application_id}")
        st.json(
            {
                "status": application.get("status"),
                "review_required": application.get("review_required"),
                "review_blockers": application.get("review_blockers"),
                "review_warnings": application.get("review_warnings"),
                "resume_document_id": application.get("resume_document_id"),
                "cover_letter_document_id": application.get("cover_letter_document_id"),
                "updated_at": application.get("updated_at"),
            }
        )

    try:
        timeline = client.get_json(f"/applications/{application_id}/timeline", token=token)
    except Exception as exc:
        st.caption(f"История статусов пока недоступна: {exc}")
        return

    if isinstance(timeline, list) and timeline:
        st.markdown("#### История статусов")
        for item in timeline:
            st.markdown(f"- {_format_status_history_entry(item)}")


def render_interview_preparation_step(
    client: CareerCopilotApiClient,
    token: str | None = None,
    *,
    show_title: bool = True,
) -> None:
    if show_title:
        st.subheader("12. Подготовка к интервью")
    st.caption(
        "Новый deterministic prep-слой вынесен в отдельный workspace. "
        "Здесь остался короткий вход без дублирования логики ответов на mock interview."
    )

    application = st.session_state.application
    if not application:
        st.info("Сначала сохраните отклик в трекере на шаге 10.")
        return

    application_status = str(application.get("status") or "").strip().lower()
    if application_status not in {
        "applied",
        "manual_applied",
        "sent_manually",
        "отправлен вручную",
    }:
        st.info(
            "Подготовка к интервью доступна после ручной отправки отклика."
        )
        return

    st.caption("Подготовка будет связана с текущим откликом.")
    with st.expander("Технические детали", expanded=False):
        st.caption(f"application_id: {application.get('id')}")
        st.caption(f"vacancy_id: {application.get('vacancy_id')}")

    render_interview_prep_workspace_tab(
        client,
        token=token,
        selection_state_key="interview_prep_workspace_flow_selection",
    )


