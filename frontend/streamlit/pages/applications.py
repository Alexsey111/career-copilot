# frontend\streamlit\pages\applications.py

from __future__ import annotations

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient
from flows.vacancy_flow import _render_vacancy_intelligence_block
from ui.formatting import (
    format_application_outcome,
    format_application_status,
    format_optional_datetime,
    format_vacancy_company,
    format_vacancy_location,
    format_vacancy_title,
)
from ui.labels import APPLICATION_REMINDER_LABELS

def render_application_dashboard(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("Дашборд откликов")
    st.caption(
        "Список внутренних записей откликов. Это не отправляет отклики на HH и не выполняет внешних действий."
    )

    if not token:
        st.warning("Войдите, чтобы открыть дашборд откликов.")
        return

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
                    "Тип": APPLICATION_REMINDER_LABELS.get(
                        str(reminder.get("reminder_type") or ""),
                        str(reminder.get("reminder_type") or ""),
                    ),
                    "Вакансия": format_vacancy_title(application.get("vacancy_title")),
                    "Возраст": f"{reminder.get('days_since_event', 0)}d",
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
            st.metric("Конверсия в applied", f"{round(conversion_to_applied * 100)}%")

        with col_avg:
            avg = analytics.get("average_time_to_apply_hours")
            st.metric("Среднее время до отклика", f"{avg}h" if avg is not None else "—")

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
            f"· {format_vacancy_title(applications_by_id[value].get('vacancy_title'))} "
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
    st.caption(f"Статус: {format_application_status(selected_application.get('status'))}")
    st.caption(f"Вакансия: {format_vacancy_title(selected_application.get('vacancy_title'))}")
    st.caption(f"Компания: {format_vacancy_company(selected_application.get('vacancy_company'))}")
    if selected_application.get("applied_at"):
        st.caption(f"Дата отправки: {format_optional_datetime(selected_application.get('applied_at'))}")
    if selected_application.get("notes"):
        st.caption(f"Заметки: {selected_application.get('notes')}")
    with st.expander("Технические детали", expanded=False):
        st.json(
            {
                "application_id": selected_application.get("id"),
                "vacancy_id": selected_application.get("vacancy_id"),
                "resume_document_id": selected_application.get("resume_document_id"),
                "cover_letter_document_id": selected_application.get("cover_letter_document_id"),
                "status": selected_application.get("status"),
                "source": selected_application.get("source"),
                "outcome": selected_application.get("outcome"),
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

    st.markdown("### Журнал действий")
    activity_log: list[dict[str, object]] = []
    try:
        activity_log_result = client.get_json(
            f"/applications/{selected_application_id}/activity-log",
            token=token,
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул ошибку HTTP {exc.response.status_code} при загрузке журнала действий")
        st.code(exc.response.text)
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend для загрузки журнала действий")
        st.code(str(exc))
    except ValueError as exc:
        st.error("Backend вернул неожиданный ответ для журнала действий")
        st.code(str(exc))
    else:
        if not isinstance(activity_log_result, list):
            st.error("Backend вернул неожиданный формат журнала действий")
            st.json(activity_log_result)
        else:
            activity_log = activity_log_result

    def _render_activity_meta(meta_json: dict[str, object] | None) -> None:
        if not meta_json:
            return

        visible_parts = []
        if meta_json.get("previous_status") or meta_json.get("new_status"):
            visible_parts.append(
                "статус: "
                f"{format_application_status(meta_json.get('previous_status'))} → "
                f"{format_application_status(meta_json.get('new_status'))}"
            )
        if meta_json.get("source"):
            visible_parts.append(f"источник: {meta_json.get('source')}")
        if meta_json.get("external_link"):
            visible_parts.append("есть внешняя ссылка")
        if meta_json.get("applied_at"):
            visible_parts.append(f"отправлено: {format_optional_datetime(meta_json.get('applied_at'))}")

        if visible_parts:
            st.caption(" · ".join(visible_parts))

        with st.expander("Технические детали", expanded=False):
            st.json(meta_json)

    if activity_log:
        for item in activity_log:
            with st.container(border=True):
                st.markdown(f"**{item.get('title') or item.get('event_type') or 'Событие'}**")
                st.caption(format_optional_datetime(item.get("created_at")))
                if item.get("description"):
                    st.write(item.get("description"))
                _render_activity_meta(item.get("meta_json") or {})
    else:
        st.caption("Журнал действий пока пуст.")

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
        with st.expander("Метаданные workflow", expanded=False):
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


