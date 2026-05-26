# frontend\streamlit\pages\system_health.py

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient
from ui.formatting import _render_inline_badges

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

app_module = sys.modules.get("app")
if app_module is not None and not hasattr(app_module, "__path__"):
    del sys.modules["app"]

_DEMO_SCENARIOS_PATH = PROJECT_ROOT / "app" / "core" / "demo_scenarios.py"
_demo_spec = importlib.util.spec_from_file_location(
    "career_copilot_demo_scenarios",
    _DEMO_SCENARIOS_PATH,
)
if _demo_spec is None or _demo_spec.loader is None:
    raise RuntimeError(f"Unable to load demo scenarios from {_DEMO_SCENARIOS_PATH}")
_demo_module = importlib.util.module_from_spec(_demo_spec)
_demo_spec.loader.exec_module(_demo_module)
get_demo_scenarios = _demo_module.get_demo_scenarios

def render_system_health(client: CareerCopilotApiClient, *, token: str | None) -> None:
    st.header("Состояние системы")
    st.caption(
        "Оперативный снимок для пилотных демо: backend, база данных, "
        "seeded-данные, счётчики и текущее активное приложение в контексте."
    )

    backend_check = client.check_backend()
    _render_inline_badges(
        [
            ("Backend доступен" if backend_check.ok else "Backend недоступен", "success" if backend_check.ok else "blocker"),
            ("Токен входа есть" if token else "Требуется вход", "success" if token else "warning"),
        ]
    )

    if not token:
        st.info("Войдите, чтобы посмотреть текущее seeded-состояние и данные по scoped-приложению.")
        return

    try:
        diagnostics = client.get_system_health_diagnostics(token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend returned HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Не удалось подключиться к backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend returned an unexpected response")
        st.code(str(exc))
        return

    if not isinstance(diagnostics, dict):
        st.error("Backend returned an unexpected system health payload")
        st.json(diagnostics)
        return

    counts = diagnostics.get("counts") or {}
    demo_state = diagnostics.get("demo_state") or {}
    current_application = diagnostics.get("current_active_application") or {}
    active_documents = diagnostics.get("active_documents") or {}
    scenario_identifiers = diagnostics.get("scenario_identifiers") or get_demo_scenarios()

    col_backend, col_db, col_seeded, col_user = st.columns(4)
    with col_backend:
        st.metric(
            "Бэкенд",
            "Доступен" if diagnostics.get("backend_reachable") else "Недоступен",
        )
    with col_db:
        st.metric(
            "База данных",
            "Доступна" if diagnostics.get("db_reachable") else "Недоступна",
        )
    with col_seeded:
        st.metric(
            "Состояние демо",
            "Готово" if demo_state.get("has_demo_data") else "Пусто",
        )
    with col_user:
        current_user_id = str(diagnostics.get("current_user_id") or "").strip()
        st.metric("Текущий пользователь", current_user_id[:8] if current_user_id else "—")

    col_vacancies, col_applications, col_documents, col_sessions = st.columns(4)
    with col_vacancies:
        st.metric("Вакансии", counts.get("vacancies", 0))
    with col_applications:
        st.metric("Отклики", counts.get("applications", 0))
    with col_documents:
        st.metric("Документы", counts.get("documents", 0))
    with col_sessions:
        st.metric("Сессии интервью", counts.get("interview_sessions", 0))

    with st.container(border=True):
        st.markdown("### Текущее активное приложение в контексте")
        if current_application:
            st.json(
                {
                    "application_id": current_application.get("id"),
                    "vacancy_id": current_application.get("vacancy_id"),
                    "status": current_application.get("status"),
                    "source": current_application.get("source"),
                    "resume_document_id": current_application.get("resume_document_id"),
                    "cover_letter_document_id": current_application.get("cover_letter_document_id"),
                    "created_at": current_application.get("created_at"),
                    "updated_at": current_application.get("updated_at"),
                }
            )
        else:
            st.info("Активное приложение в контексте пока не найдено.")

    with st.container(border=True):
        st.markdown("### Активные документы в контексте")
        resume_document = active_documents.get("resume")
        cover_letter_document = active_documents.get("cover_letter")
        if not resume_document and not cover_letter_document:
            st.caption("Активные документы в контексте пока недоступны.")
        else:
            for label, document in (
                ("Резюме", resume_document),
                ("Сопроводительное письмо", cover_letter_document),
            ):
                with st.expander(label, expanded=False):
                    if not document:
                        st.caption("Активный документ отсутствует.")
                        continue
                    st.json(
                        {
                            "document_id": document.get("id"),
                            "vacancy_id": document.get("vacancy_id"),
                            "document_kind": document.get("document_kind"),
                            "version_label": document.get("version_label"),
                            "review_status": document.get("review_status"),
                            "is_active": document.get("is_active"),
                            "created_at": document.get("created_at"),
                            "updated_at": document.get("updated_at"),
                        }
                    )

    with st.expander("Демо-сценарии", expanded=True):
        for scenario in scenario_identifiers:
            if not isinstance(scenario, dict):
                continue
            label = str(scenario.get("label") or scenario.get("code") or "Scenario")
            code = str(scenario.get("code") or "").strip()
            description = str(scenario.get("description") or "").strip()
            with st.container(border=True):
                st.markdown(f"**{label}**")
                if code:
                    st.caption(code)
                if description:
                    st.write(description)

    with st.expander("Команды сброса и проверки", expanded=False):
        st.code(
            "python scripts/reset_demo_environment.py\n"
            "python scripts/check_demo_trust_states.py",
            language="bash",
        )


