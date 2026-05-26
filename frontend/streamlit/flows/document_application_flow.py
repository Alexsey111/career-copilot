# frontend\streamlit\flows\document_application_flow.py

from __future__ import annotations

import httpx
import streamlit as st
import streamlit.components.v1 as st_components

from api_client import CareerCopilotApiClient
from components import (
    render_document_review_workspace_tab,
    render_interview_prep_workspace_tab,
)


def _scroll_to_step9_top() -> None:
    st_components.html(
        """
        <script>
        const anchor = window.parent.document.getElementById("step-9-document-review");
        if (anchor) {
            anchor.scrollIntoView({behavior: "smooth", block: "start"});
        } else {
            window.parent.scrollTo({top: 0, behavior: "smooth"});
        }
        </script>
        """,
        height=0,
    )


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
    st.markdown('<div id="step-9-document-review"></div>', unsafe_allow_html=True)
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

    if not resume_ready or not cover_letter_ready:
        st.info(
            "Для перехода к шагу 10 нужно выбрать оба документа: "
            "резюме и сопроводительное письмо."
        )
    else:
        st.success("Оба документа выбраны. Можно переходить к шагу 10.")

    if st.session_state.pop("document_review_step9_return_notice", False):
        _scroll_to_step9_top()
        if not resume_ready or not cover_letter_ready:
            st.info("Документ выбран. Теперь выберите второй документ ниже.")
        else:
            st.success("Документ выбран. Оба документа готовы для шага 10.")

    vacancy = st.session_state.vacancy or {}
    current_vacancy_id = vacancy.get("vacancy_id") or vacancy.get("id")
    render_document_review_workspace_tab(
        client,
        token=token,
        selection_state_key="document_review_workspace_step9_selection",
        current_vacancy_id=str(current_vacancy_id) if current_vacancy_id else None,
        show_only_current_vacancy=True,
    )


def render_application_creation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("10. Создание записи отклика")

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
                "review_required": application.get("review_required"),
                "review_blockers": application.get("review_blockers"),
                "review_warnings": application.get("review_warnings"),
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
            use_container_width=True,
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


def render_application_tracking_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("12. Трекинг отклика")

    application = st.session_state.application
    if not application:
        st.info("Сначала создайте запись отклика на шаге 10.")
        return

    application_id = application.get("id")
    if not application_id:
        st.error("В записи отклика не найден application_id.")
        st.json(application)
        return

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
            st.markdown(
                f"- {item.get('created_at')}: "
                f"{item.get('previous_status') or '—'} → {item.get('new_status')}"
            )


def render_interview_preparation_step(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.subheader("13. Подготовка к интервью")
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


