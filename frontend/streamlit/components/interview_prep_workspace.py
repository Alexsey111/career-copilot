# frontend\streamlit\components\interview_prep_workspace.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient


@dataclass(frozen=True, slots=True)
class InterviewPrepSessionDescriptor:
    session_id: str
    application_id: str
    vacancy_id: str
    prep_status: str
    readiness_score: int | None


def _format_score(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{round(float(value))} / 100"
    except (TypeError, ValueError):
        return str(value)


def _humanize_prep_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    labels = {
        "draft": "черновик",
        "ready": "готова",
        "blocked": "нужны подтверждения",
        "in_progress": "в работе",
    }
    return labels.get(status, status or "—")


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _evidence_status_icon(fact_status: str | None) -> str:
    status = str(fact_status or "").strip().lower()
    if status in {"confirmed", "user_provided"}:
        return "✅"
    if status in {"needs_confirmation", "partial"}:
        return "⚠️"
    if status == "rejected":
        return "🛑"
    return "❌"


def _fact_status_badge(fact_status: str | None) -> str:
    status = str(fact_status or "").strip().lower()
    labels = {
        "confirmed": "✓ Подтверждено пользователем",
        "user_provided": "✓ Есть в резюме/профиле",
        "needs_confirmation": "⚠ Требует подтверждения",
        "partial": "⚠ Подтверждено частично",
        "rejected": "✗ Отклонено",
        "unverified": "⚠ Требует проверки",
    }
    return labels.get(status, "⚠ Требует проверки")


def _humanize_reason(reason: Any) -> str:
    text = str(reason or "").strip()
    if not text or text == "—":
        return "Этот пример связан с компетенцией из вакансии."

    lowered = text.lower()
    replacements = {
        "keyword overlap": "Совпадает с требованиями вакансии",
        "skills overlap": "Навыки совпадают с требованиями вакансии",
        "snippet text overlap": "Описание проекта совпадает с требованиями вакансии",
        "related skill overlap": "Связанный навык поддерживает требование вакансии",
        "recommended": "Рекомендовано для ответа на этот вопрос",
    }
    for key, label in replacements.items():
        if key in lowered:
            return label
    return text


def _humanize_strength(value: Any) -> str:
    strength = str(value or "").strip().lower()
    return {
        "strong": "сильное подтверждение",
        "medium": "частичное подтверждение",
        "weak": "слабое подтверждение",
    }.get(strength, "требует проверки")


def _collect_evidence_by_competency(
    *,
    questions: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}

    for question in questions:
        competency_key = _normalize_key(question.get("competency_key"))
        if not competency_key:
            continue

        for item in question.get("recommended_evidence") or []:
            result.setdefault(competency_key, []).append(item)

    for item in evidence_links:
        competency_key = _normalize_key(item.get("competency_key"))
        if not competency_key:
            continue
        result.setdefault(competency_key, []).append(item)

    return result


def _best_fact_status(items: list[dict[str, Any]]) -> str | None:
    statuses = {
        str(item.get("fact_status") or "").strip().lower()
        for item in items
        if str(item.get("fact_status") or "").strip()
    }
    if "confirmed" in statuses:
        return "confirmed"
    if "user_provided" in statuses:
        return "user_provided"
    if "needs_confirmation" in statuses:
        return "needs_confirmation"
    if "partial" in statuses:
        return "partial"
    if statuses:
        return sorted(statuses)[0]
    return None


def _render_readiness_panel(readiness: dict[str, Any] | None) -> None:
    readiness = readiness or {}
    blockers = readiness.get("blockers") or []
    warnings = readiness.get("warnings") or []

    if readiness.get("ready"):
        st.success("Готово к подготовке к интервью ✅")
    else:
        st.warning("Нужно подтвердить факты для полной подготовки ⚠️")

    col_ready, col_blockers, col_warnings, col_score = st.columns(4)

    with col_ready:
        st.metric("Готово", "Да" if readiness.get("ready") else "Нет")
    with col_blockers:
        st.metric("Блокеры", len(blockers))
    with col_warnings:
        st.metric("Предупреждения", len(warnings))
    with col_score:
        st.metric("Оценка", _format_score(readiness.get("score")))

    if blockers:
        st.markdown("**Блокеры**")
        for blocker in blockers:
            st.markdown(f"- {blocker}")
        st.caption(
            "Это не ошибка. Система нашла возможные доказательства, "
            "но они ещё не подтверждены пользователем. Подтвердите релевантный опыт "
            "или используйте вопросы как черновик подготовки."
        )

    if warnings:
        st.markdown("**Предупреждения**")
        for warning in warnings:
            st.markdown(f"- {warning}")


def _render_competency_coverage(
    *,
    competency_map: dict[str, Any] | None,
    questions: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
    weak_areas: list[dict[str, Any]],
) -> None:
    competency_map = competency_map or {}
    required_skills = competency_map.get("required_skills") or []

    st.markdown("### Покрытие компетенций доказательствами")
    st.caption(
        "Показывает, какие требования вакансии уже подтверждены, "
        "какие требуют подтверждения, а где доказательств пока нет."
    )

    if not required_skills:
        st.info("Обязательные компетенции не извлечены.")
        return

    evidence_by_competency = _collect_evidence_by_competency(
        questions=questions,
        evidence_links=evidence_links,
    )
    weak_by_competency = {
        _normalize_key(item.get("competency_key")): item
        for item in weak_areas
        if item.get("competency_key")
    }

    rows = []
    for skill in required_skills:
        key = _normalize_key(skill.get("key"))
        label = skill.get("label") or skill.get("key") or "—"
        evidence_items = evidence_by_competency.get(key, [])
        fact_status = _best_fact_status(evidence_items)

        if fact_status in {"confirmed", "user_provided"}:
            status_text = "Подтверждено"
        elif fact_status in {"needs_confirmation", "partial"}:
            status_text = "Нужно подтвердить"
        elif key in weak_by_competency:
            status_text = "Нет подтверждённого evidence"
        else:
            status_text = "Не определено"

        rows.append(
            {
                "Статус": _evidence_status_icon(fact_status if evidence_items else None),
                "Компетенция": label,
                "Покрытие": status_text,
                "Найдено примеров": len(evidence_items),
                "Комментарий": (
                    weak_by_competency.get(key, {}).get("message")
                    if key in weak_by_competency
                    else "Есть подтверждающие примеры"
                    if evidence_items
                    else "Примеры не найдены"
                ),
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.caption(
        "✅ подтверждено · ⚠️ найдено, но требует подтверждения · "
        "❌ подтверждающих примеров нет"
    )


def _render_competency_map(competency_map: dict[str, Any] | None) -> None:
    competency_map = competency_map or {}

    st.markdown("### Карта компетенций")
    col_skills, col_behavioral = st.columns(2)

    with col_skills:
        st.markdown("#### Обязательные навыки")
        required_skills = competency_map.get("required_skills") or []
        if required_skills:
            for item in required_skills:
                st.markdown(f"- {item.get('label') or item.get('key')}")
        else:
            st.caption("Обязательные навыки не извлечены.")

    with col_behavioral:
        st.markdown("#### Поведенческие сигналы")
        behavioral_signals = competency_map.get("behavioral_signals") or []
        if behavioral_signals:
            for signal in behavioral_signals:
                st.markdown(f"- {signal}")
        else:
            st.caption("Поведенческие сигналы не извлечены.")

    col_seniority, col_domain = st.columns(2)

    with col_seniority:
        st.markdown("#### Ожидания по уровню")
        seniority = competency_map.get("seniority_expectations") or {}
        if seniority:
            st.write(f"Уровень: {seniority.get('level') or '—'}")
            for signal in seniority.get("signals") or []:
                st.markdown(f"- {signal}")
        else:
            st.caption("Ожидания по уровню не извлечены.")

    with col_domain:
        st.markdown("#### Ожидания по домену")
        domain_expectations = competency_map.get("domain_expectations") or []
        if domain_expectations:
            for domain in domain_expectations:
                st.markdown(f"- {domain}")
        else:
            st.caption("Ожидания по домену не извлечены.")


def _render_suggested_answer(answer: dict[str, Any] | None) -> None:
    if not isinstance(answer, dict) or not answer:
        return

    with st.expander("Черновик ответа", expanded=False):
        st.caption("Черновик ответа. Проверьте и адаптируйте под свой реальный опыт.")

        fields = [
            ("Situation", answer.get("situation")),
            ("Task", answer.get("task")),
            ("Action", answer.get("action")),
            ("Result", answer.get("result")),
        ]
        for label, value in fields:
            value_text = str(value or "").strip()
            if value_text:
                st.markdown(f"**{label}:** {value_text}")

    tech_stack = [
        str(item).strip()
        for item in (answer.get("tech_stack") or [])
        if str(item).strip()
    ]
    if tech_stack:
        with st.expander("Технологии", expanded=False):
            st.markdown(", ".join(tech_stack))

    tradeoffs = [
        str(item).strip()
        for item in (answer.get("tradeoffs") or [])
        if str(item).strip()
    ]
    if tradeoffs:
        with st.expander("Компромиссы и ограничения", expanded=False):
            for item in tradeoffs:
                st.markdown(f"- {item}")

    talking_points = [
        str(item).strip()
        for item in (answer.get("talking_points") or [])
        if str(item).strip()
    ]
    if talking_points:
        with st.expander("Что подчеркнуть на интервью", expanded=False):
            for item in talking_points:
                st.markdown(f"- {item}")


def _render_question_group(questions: list[dict[str, Any]]) -> None:
    if not questions:
        st.info("Сгенерированных вопросов пока нет.")
        return

    st.markdown("### Вопросы")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        grouped.setdefault(str(question.get("category") or "unknown"), []).append(question)

    for category, items in grouped.items():
        with st.expander(f"{category} ({len(items)})", expanded=category in {"technical", "gap-risk"}):
            for question in items:
                with st.container(border=True):
                    st.markdown(f"**{question.get('prompt') or 'Question'}**")
                    if question.get("answer_format"):
                        st.caption(f"Формат ответа: {question.get('answer_format')}")
                    if question.get("competency_name") or question.get("competency_key"):
                        st.caption(
                            "Компетенция: "
                            f"{question.get('competency_name') or question.get('competency_key')}"
                        )

                    _render_suggested_answer(question.get("suggested_answer"))

                    evidence = question.get("recommended_evidence") or []
                    with st.expander("Почему система предлагает этот пример", expanded=False):
                        if evidence:
                            for item in evidence:
                                fact_status = _fact_status_badge(item.get("fact_status"))
                                st.markdown(
                                    f"- {fact_status} · {item.get('title')}"
                                )
                                reason = item.get("reason")
                                if reason:
                                    st.caption(_humanize_reason(reason))
                        else:
                            st.caption("Пока не привязано подтверждённое доказательство.")


def _render_question_supporting_evidence(
    client: CareerCopilotApiClient,
    *,
    question: dict[str, Any],
    selected_session: dict[str, Any],
    token: str | None,
) -> None:
    recommended = question.get("recommended_evidence") or []
    evidence_links = selected_session.get("evidence_links") or []
    question_id = str(question.get("question_id") or "").strip()

    if not recommended and evidence_links:
        recommended = [
            {
                "achievement_id": item.get("achievement_id"),
                "title": item.get("achievement_title"),
                "score": item.get("score"),
                "reason": item.get("reason"),
            }
            for item in evidence_links
            if str(item.get("question_id") or "").strip() == question_id
        ]

    st.markdown("##### Поддерживающие доказательства")
    if not recommended:
        st.caption("Для этого вопроса ещё не выбраны поддерживающие доказательства.")
        return

    for item in recommended:
        evidence_id = str(item.get("achievement_id") or "").strip()
        title = str(item.get("title") or "Подтверждающий опыт").strip()
        reason = str(item.get("reason") or "").strip() or "—"
        score = _format_score(item.get("score"))

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"Почему это поможет в ответе: {_humanize_reason(reason)}")

            if not evidence_id:
                st.caption("Детали этого доказательства пока недоступны.")
                continue

            try:
                snippet = client.get_evidence_snippet(evidence_id, token=token)
            except httpx.HTTPStatusError as exc:
                st.caption(f"Не удалось загрузить детали доказательства: HTTP {exc.response.status_code}")
                continue
            except httpx.RequestError as exc:
                st.caption(f"Не удалось загрузить детали доказательства: {exc}")
                continue
            except ValueError as exc:
                st.caption(f"Не удалось загрузить детали доказательства: {exc}")
                continue

            if not isinstance(snippet, dict):
                st.caption("Backend вернул неожиданные детали доказательства.")
                continue

            fact_status = snippet.get("fact_status") or "—"
            strength = snippet.get("evidence_strength") or "—"
            st.caption(f"{_fact_status_badge(str(fact_status))} · {_humanize_strength(strength)}")

            star_summary = snippet.get("star_summary") or snippet.get("star_summary_json") or {}
            if isinstance(star_summary, dict) and star_summary:
                star_parts = [
                    f"{key}={value}"
                    for key, value in star_summary.items()
                    if value not in (None, "", [])
                ]
                if star_parts:
                    st.caption("STAR-превью: " + ", ".join(star_parts))

            snippet_text = str(snippet.get("snippet_text") or "").strip()
            if snippet_text:
                st.write(snippet_text)


def _render_evidence_links(evidence_links: list[dict[str, Any]]) -> None:
    st.markdown("### Связки STAR-доказательств")
    if not evidence_links:
        st.caption("Связок доказательств пока нет.")
        return

    rows = []
    for item in evidence_links:
        rows.append(
            {
                "Вопрос": str(item.get("question_category") or "—"),
                "Компетенция": item.get("competency_key") or "—",
                "Достижение": item.get("achievement_title") or "—",
                "Почему подходит": _humanize_reason(item.get("reason")),
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_weak_areas(weak_areas: list[dict[str, Any]]) -> None:
    st.markdown("### Слабые зоны")
    if not weak_areas:
        st.success("Детерминированные слабые зоны не обнаружены.")
        return

    for item in weak_areas:
        severity = str(item.get("severity") or "").lower()
        text = f"{item.get('message') or 'Weak area'}"
        if severity == "blocker":
            st.error(text)
        elif severity == "warning":
            st.warning(text)
        else:
            st.info(text)
        if item.get("category") or item.get("competency_key"):
            st.caption(
                f"{item.get('category') or 'category'} · {item.get('competency_key') or 'competency'}"
            )


def _render_create_action(
    client: CareerCopilotApiClient,
    *,
    token: str | None,
    selection_state_key: str,
) -> None:
    application = st.session_state.get("application")
    if not application:
        st.info("В сессии Streamlit нет текущего отклика. Сначала создайте отклик со статусом applied.")
        return

    if str(application.get("status") or "").lower() != "applied":
        st.info("Подготовка к интервью доступна после перевода отклика в статус applied.")
        return

    application_id = str(application.get("id") or "").strip()
    if not application_id:
        st.warning("У текущего отклика нет id.")
        return

    st.caption("Сессия будет связана с текущим откликом.")
    with st.expander("Технические детали", expanded=False):
        st.caption(f"application_id: {application_id}")
        st.caption(f"vacancy_id: {application.get('vacancy_id')}")

    button_key = f"{selection_state_key}_create_interview_prep_session"

    if st.button(
        "Создать сессию подготовки к интервью",
        type="primary",
        use_container_width=True,
        key=button_key,
    ):
        try:
            session = client.create_interview_prep_session(
                application_id=application_id,
                token=token,
            )
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend вернул HTTP {exc.response.status_code}")
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

        if not isinstance(session, dict):
            st.error("Backend вернул неожиданный формат сессии")
            st.json(session)
            return

        st.session_state[selection_state_key] = str(session.get("id") or "")
        st.success("Сессия подготовки к интервью создана")
        st.rerun()


def render_interview_prep_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
    selection_state_key: str = "interview_prep_workspace_selection",
) -> None:
    st.header("Подготовка к интервью")
    st.caption(
        "Детерминированный слой подготовки: карта компетенций, генерация вопросов, "
        "связки с доказательствами, слабые зоны и готовность."
    )

    if not token:
        st.warning("Войдите, чтобы открыть подготовку к интервью.")
        return

    _render_create_action(
        client,
        token=token,
        selection_state_key=selection_state_key,
    )

    try:
        sessions = client.list_interview_prep_sessions(token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул HTTP {exc.response.status_code}")
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
        st.error("Backend вернул неожиданный список сессий")
        st.json(sessions)
        return

    current_application = st.session_state.get("application") or {}
    current_application_id = str(current_application.get("id") or "").strip()

    if current_application_id:
        sessions = [
            item for item in sessions
            if str(item.get("application_id") or "").strip() == current_application_id
        ]

    if not sessions:
        st.info("Сессии подготовки к интервью пока не созданы.")
        return

    normalized_sessions: list[InterviewPrepSessionDescriptor] = []
    for item in sessions:
        session_id = str(item.get("id") or "").strip()
        if not session_id:
            continue
        normalized_sessions.append(
            InterviewPrepSessionDescriptor(
                session_id=session_id,
                application_id=str(item.get("application_id") or ""),
                vacancy_id=str(item.get("vacancy_id") or ""),
                prep_status=str(item.get("prep_status") or "draft"),
                readiness_score=item.get("readiness_score"),
            )
        )

    if not normalized_sessions:
        st.warning("Не найдено доступных сессий подготовки.")
        return

    total_count = len(normalized_sessions)
    ready_count = sum(1 for item in normalized_sessions if item.prep_status == "ready")
    draft_count = sum(1 for item in normalized_sessions if item.prep_status == "draft")
    readiness_values = [
        int(item.readiness_score)
        for item in normalized_sessions
        if item.readiness_score is not None
    ]
    average_readiness = (
        round(sum(readiness_values) / len(readiness_values))
        if readiness_values
        else None
    )

    col_total, col_ready, col_draft, col_avg = st.columns(4)
    with col_total:
        st.metric("Всего", total_count)
    with col_ready:
        st.metric("Готово", ready_count)
    with col_draft:
        st.metric("Черновиков", draft_count)
    with col_avg:
        st.metric(
            "Средняя оценка",
            f"{average_readiness} / 100" if average_readiness is not None else "—",
        )

    session_display_names = {
        item.session_id: f"Сессия подготовки {idx}"
        for idx, item in enumerate(normalized_sessions, start=1)
    }

    rows = [
        {
            "Сессия": session_display_names[item.session_id],
            "Отклик": "текущий" if item.application_id else "—",
            "Статус": _humanize_prep_status(item.prep_status),
            "Готовность": _format_score(item.readiness_score),
        }
        for item in normalized_sessions
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    options = [item.session_id for item in normalized_sessions]
    labels = {
        item.session_id: (
            f"{session_display_names[item.session_id]} · "
            f"{_humanize_prep_status(item.prep_status)} · "
            f"{_format_score(item.readiness_score)}"
        )
        for item in normalized_sessions
    }
    selected_session_id = st.session_state.get(selection_state_key)
    if selected_session_id not in options:
        selected_session_id = options[0]

    selected_session_id = st.selectbox(
        "Выберите сессию",
        options=options,
        index=options.index(selected_session_id),
        format_func=lambda value: labels.get(value, value),
        key=f"{selection_state_key}_picker",
    )
    st.session_state[selection_state_key] = selected_session_id

    try:
        selected_session = client.get_interview_prep_session(selected_session_id, token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend вернул HTTP {exc.response.status_code}")
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
        st.error("Backend вернул неожиданный формат сессии")
        st.json(selected_session)
        return

    st.markdown("### Сессия подготовки")
    st.caption(f"Статус: {_humanize_prep_status(selected_session.get('prep_status'))}")
    st.caption(f"Готовность: {_format_score(selected_session.get('readiness_score'))}")
    st.caption("Связана с текущим откликом")

    with st.expander("Технические детали", expanded=False):
        st.caption(f"id: {selected_session.get('id')}")
        st.caption(f"application_id: {selected_session.get('application_id')}")
        st.caption(f"vacancy_id: {selected_session.get('vacancy_id')}")
        st.caption(f"prep_status: {selected_session.get('prep_status')}")
        st.caption(f"readiness_score: {selected_session.get('readiness_score')}")

    _render_readiness_panel(selected_session.get("readiness"))
    st.divider()
    _render_competency_coverage(
        competency_map=selected_session.get("competency_map"),
        questions=selected_session.get("questions") or [],
        evidence_links=selected_session.get("evidence_links") or [],
        weak_areas=selected_session.get("weak_areas") or [],
    )
    st.divider()
    _render_competency_map(selected_session.get("competency_map"))
    st.divider()
    _render_question_group(selected_session.get("questions") or [])
    st.divider()
    st.markdown("### Provenance доказательств по вопросам")
    questions = selected_session.get("questions") or []
    if not questions:
        st.caption("Вопросов пока нет.")
    else:
        for question in questions:
            with st.container(border=True):
                st.markdown(f"**{question.get('prompt') or 'Question'}**")
                if question.get("answer_format"):
                    st.caption(f"Формат ответа: {question.get('answer_format')}")
                if question.get("competency_name") or question.get("competency_key"):
                    st.caption(
                        "Компетенция: "
                        f"{question.get('competency_name') or question.get('competency_key')}"
                    )
                _render_question_supporting_evidence(
                    client,
                    question=question,
                    selected_session=selected_session,
                    token=token,
                )
    st.divider()
    _render_evidence_links(selected_session.get("evidence_links") or [])
    st.divider()
    _render_weak_areas(selected_session.get("weak_areas") or [])

    # Raw JSON intentionally hidden to keep the operator view compact.
