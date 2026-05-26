# frontend\streamlit\flows\mvp_flow.py

from __future__ import annotations

import streamlit as st

from api_client import CareerCopilotApiClient
from flows.document_application_flow import (
    render_application_creation_step,
    render_application_status_update_step,
    render_application_tracking_step,
    render_cover_letter_generation_step,
    render_document_approval_step,
    render_interview_preparation_step,
    render_resume_generation_step,
)
from flows.resume_intake import (
    render_achievements_step,
    render_resume_import_step,
    render_resume_upload_step,
    render_structured_profile_step,
)
from flows.vacancy_flow import (
    render_vacancy_analysis_step,
    render_vacancy_import_step,
)


def render_mvp_flow(client: CareerCopilotApiClient, token: str | None = None) -> None:
    st.header("MVP-сценарий")

    if not token:
        st.warning("Войдите или зарегистрируйтесь, чтобы пройти MVP-сценарий.")
        return

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

    render_application_tracking_step(client, token=token)

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
