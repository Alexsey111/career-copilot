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


def _render_readiness_panel(readiness: dict[str, Any] | None) -> None:
    readiness = readiness or {}
    blockers = readiness.get("blockers") or []
    warnings = readiness.get("warnings") or []

    if readiness.get("ready"):
        st.success("Ready for interview prep ✅")
    else:
        st.error("Prep is blocked ❌")

    col_ready, col_blockers, col_warnings, col_score = st.columns(4)

    with col_ready:
        st.metric("Ready", "Yes" if readiness.get("ready") else "No")
    with col_blockers:
        st.metric("Blockers", len(blockers))
    with col_warnings:
        st.metric("Warnings", len(warnings))
    with col_score:
        st.metric("Score", _format_score(readiness.get("score")))

    if blockers:
        st.markdown("**Blockers**")
        for blocker in blockers:
            st.markdown(f"- {blocker}")

    if warnings:
        st.markdown("**Warnings**")
        for warning in warnings:
            st.markdown(f"- {warning}")


def _render_competency_map(competency_map: dict[str, Any] | None) -> None:
    competency_map = competency_map or {}

    st.markdown("### Competency map")
    col_skills, col_behavioral = st.columns(2)

    with col_skills:
        st.markdown("#### Required skills")
        required_skills = competency_map.get("required_skills") or []
        if required_skills:
            for item in required_skills:
                st.markdown(f"- {item.get('label') or item.get('key')}")
        else:
            st.caption("No required skills extracted.")

    with col_behavioral:
        st.markdown("#### Behavioral signals")
        behavioral_signals = competency_map.get("behavioral_signals") or []
        if behavioral_signals:
            for signal in behavioral_signals:
                st.markdown(f"- {signal}")
        else:
            st.caption("No behavioral signals extracted.")

    col_seniority, col_domain = st.columns(2)

    with col_seniority:
        st.markdown("#### Seniority expectations")
        seniority = competency_map.get("seniority_expectations") or {}
        if seniority:
            st.write(f"Level: {seniority.get('level') or '—'}")
            for signal in seniority.get("signals") or []:
                st.markdown(f"- {signal}")
        else:
            st.caption("No seniority expectations extracted.")

    with col_domain:
        st.markdown("#### Domain expectations")
        domain_expectations = competency_map.get("domain_expectations") or []
        if domain_expectations:
            for domain in domain_expectations:
                st.markdown(f"- {domain}")
        else:
            st.caption("No domain expectations extracted.")


def _render_question_group(questions: list[dict[str, Any]]) -> None:
    if not questions:
        st.info("No generated questions.")
        return

    st.markdown("### Questions")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        grouped.setdefault(str(question.get("category") or "unknown"), []).append(question)

    for category, items in grouped.items():
        with st.expander(f"{category} ({len(items)})", expanded=category in {"technical", "gap-risk"}):
            for question in items:
                with st.container(border=True):
                    st.markdown(f"**{question.get('prompt') or 'Question'}**")
                    if question.get("answer_format"):
                        st.caption(f"Answer format: {question.get('answer_format')}")
                    if question.get("competency_name") or question.get("competency_key"):
                        st.caption(
                            "Competency: "
                            f"{question.get('competency_name') or question.get('competency_key')}"
                        )

                    evidence = question.get("recommended_evidence") or []
                    if evidence:
                        st.markdown("Recommended STAR evidence")
                        for item in evidence:
                            st.markdown(
                                f"- {item.get('title')}: {_format_score(item.get('score'))}"
                            )
                            reason = item.get("reason")
                            if reason:
                                st.caption(reason)
                    else:
                        st.caption("No confirmed evidence linked yet.")


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

    st.markdown("##### Supporting evidence")
    if not recommended:
        st.caption("No supporting evidence selected for this question yet.")
        return

    for item in recommended:
        evidence_id = str(item.get("achievement_id") or "").strip()
        title = str(item.get("title") or "Evidence").strip()
        reason = str(item.get("reason") or "").strip() or "—"
        score = _format_score(item.get("score"))

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"evidence_id: {evidence_id or '—'}")
            st.caption(f"reason: {reason}")
            st.caption(f"score: {score}")

            if not evidence_id:
                st.caption("No evidence id available for snippet lookup.")
                continue

            try:
                snippet = client.get_evidence_snippet(evidence_id, token=token)
            except httpx.HTTPStatusError as exc:
                st.caption(f"Snippet lookup failed: HTTP {exc.response.status_code}")
                continue
            except httpx.RequestError as exc:
                st.caption(f"Snippet lookup failed: {exc}")
                continue
            except ValueError as exc:
                st.caption(f"Snippet lookup failed: {exc}")
                continue

            if not isinstance(snippet, dict):
                st.caption("Snippet lookup returned an unexpected payload.")
                continue

            fact_status = snippet.get("fact_status") or "—"
            strength = snippet.get("evidence_strength") or "—"
            st.caption(f"fact_status: {fact_status} · strength: {strength}")

            star_summary = snippet.get("star_summary") or snippet.get("star_summary_json") or {}
            if isinstance(star_summary, dict) and star_summary:
                star_parts = [
                    f"{key}={value}"
                    for key, value in star_summary.items()
                    if value not in (None, "", [])
                ]
                if star_parts:
                    st.caption("STAR preview: " + ", ".join(star_parts))

            snippet_text = str(snippet.get("snippet_text") or "").strip()
            if snippet_text:
                st.write(snippet_text)


def _render_evidence_links(evidence_links: list[dict[str, Any]]) -> None:
    st.markdown("### STAR evidence links")
    if not evidence_links:
        st.caption("No evidence links available.")
        return

    rows = []
    for item in evidence_links:
        rows.append(
            {
                "Question": str(item.get("question_category") or "—"),
                "Competency": item.get("competency_key") or "—",
                "Achievement": item.get("achievement_title") or "—",
                "Score": _format_score(item.get("score")),
                "Reason": item.get("reason") or "—",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_weak_areas(weak_areas: list[dict[str, Any]]) -> None:
    st.markdown("### Weak areas")
    if not weak_areas:
        st.success("No deterministic weak areas detected.")
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
) -> None:
    application = st.session_state.get("application")
    if not application:
        st.info("No current application in Streamlit session. Create an applied application first.")
        return

    if str(application.get("status") or "").lower() != "applied":
        st.info("Interview prep is available after the application is marked as applied.")
        return

    application_id = str(application.get("id") or "").strip()
    if not application_id:
        st.warning("Current application has no id.")
        return

    st.caption(f"application_id: {application_id}")
    st.caption(f"vacancy_id: {application.get('vacancy_id')}")

    if st.button(
        "Create interview prep session",
        type="primary",
        use_container_width=True,
        key="create_interview_prep_session",
    ):
        try:
            session = client.create_interview_prep_session(
                application_id=application_id,
                token=token,
            )
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend returned HTTP {exc.response.status_code}")
            st.code(exc.response.text)
            return
        except httpx.RequestError as exc:
            st.error("Unable to connect to backend")
            st.code(str(exc))
            return
        except ValueError as exc:
            st.error("Backend returned an unexpected response")
            st.code(str(exc))
            return

        if not isinstance(session, dict):
            st.error("Backend returned unexpected prep session payload")
            st.json(session)
            return

        st.session_state["interview_prep_workspace_selection"] = str(session.get("id") or "")
        st.success("Interview prep session created")
        st.rerun()


def render_interview_prep_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
    selection_state_key: str = "interview_prep_workspace_selection",
) -> None:
    st.header("Interview Prep Workspace")
    st.caption(
        "Deterministic prep layer: competency map, question generation, evidence linking, "
        "weak areas, and readiness."
    )

    _render_create_action(client, token=token)

    try:
        sessions = client.list_interview_prep_sessions(token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend returned HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Unable to connect to backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend returned an unexpected response")
        st.code(str(exc))
        return

    if not isinstance(sessions, list):
        st.error("Backend returned an unexpected prep session list")
        st.json(sessions)
        return

    if not sessions:
        st.info("No interview prep sessions created yet.")
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
        st.warning("No valid prep session ids found.")
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
        st.metric("Total", total_count)
    with col_ready:
        st.metric("Ready", ready_count)
    with col_draft:
        st.metric("Draft", draft_count)
    with col_avg:
        st.metric(
            "Average score",
            f"{average_readiness} / 100" if average_readiness is not None else "—",
        )

    rows = [
        {
            "Session": item.session_id[:8],
            "Application": item.application_id[:8] if item.application_id else "—",
            "Vacancy": item.vacancy_id[:8] if item.vacancy_id else "—",
            "Status": item.prep_status,
            "Readiness": _format_score(item.readiness_score),
        }
        for item in normalized_sessions
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    options = [item.session_id for item in normalized_sessions]
    labels = {
        item.session_id: (
            f"{item.prep_status} · {item.session_id[:8]} · "
            f"app {item.application_id[:8] if item.application_id else '—'}"
        )
        for item in normalized_sessions
    }
    selected_session_id = st.session_state.get(selection_state_key)
    if selected_session_id not in options:
        selected_session_id = options[0]

    selected_session_id = st.selectbox(
        "Choose prep session",
        options=options,
        index=options.index(selected_session_id),
        format_func=lambda value: labels.get(value, value),
        key=f"{selection_state_key}_picker",
    )
    st.session_state[selection_state_key] = selected_session_id

    try:
        selected_session = client.get_interview_prep_session(selected_session_id, token=token)
    except httpx.HTTPStatusError as exc:
        st.error(f"Backend returned HTTP {exc.response.status_code}")
        st.code(exc.response.text)
        return
    except httpx.RequestError as exc:
        st.error("Unable to connect to backend")
        st.code(str(exc))
        return
    except ValueError as exc:
        st.error("Backend returned an unexpected response")
        st.code(str(exc))
        return

    if not isinstance(selected_session, dict):
        st.error("Backend returned an unexpected prep session payload")
        st.json(selected_session)
        return

    st.markdown("### Session details")
    st.json(
        {
            "id": selected_session.get("id"),
            "application_id": selected_session.get("application_id"),
            "vacancy_id": selected_session.get("vacancy_id"),
            "prep_status": selected_session.get("prep_status"),
            "readiness_score": selected_session.get("readiness_score"),
            "created_at": selected_session.get("created_at"),
            "updated_at": selected_session.get("updated_at"),
        }
    )

    _render_readiness_panel(selected_session.get("readiness"))
    st.divider()
    _render_competency_map(selected_session.get("competency_map"))
    st.divider()
    _render_question_group(selected_session.get("questions") or [])
    st.divider()
    st.markdown("### Question evidence provenance")
    questions = selected_session.get("questions") or []
    if not questions:
        st.caption("No questions available.")
    else:
        for question in questions:
            with st.container(border=True):
                st.markdown(f"**{question.get('prompt') or 'Question'}**")
                if question.get("answer_format"):
                    st.caption(f"Answer format: {question.get('answer_format')}")
                if question.get("competency_name") or question.get("competency_key"):
                    st.caption(
                        "Competency: "
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

    with st.expander("Raw JSON", expanded=False):
        st.json(selected_session)
