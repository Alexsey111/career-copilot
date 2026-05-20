from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from api_client import CareerCopilotApiClient


def _format_count(value: Any) -> str:
    try:
        return str(int(value or 0))
    except (TypeError, ValueError):
        return "0"


def _render_application_patterns(patterns: dict[str, Any] | None) -> None:
    patterns = patterns or {}
    st.markdown("### Application Pattern Insights")
    col_sent, col_interviews, col_offers, col_conv = st.columns(4)

    with col_sent:
        st.metric("Applications sent", patterns.get("applications_sent", 0))
    with col_interviews:
        st.metric("Interviews reached", patterns.get("interviews_reached", 0))
    with col_offers:
        st.metric("Offers", patterns.get("offers_count", 0))
    with col_conv:
        st.metric(
            "Conversion to interview",
            f"{round(float(patterns.get('conversion_to_interview') or 0) * 100)}%",
        )

    st.caption(
        "Most common rejection stage: "
        f"{patterns.get('most_common_rejection_stage') or '—'} "
        f"({patterns.get('most_common_rejection_stage_count', 0)})"
    )
    st.caption(
        "Conversion to offer: "
        f"{round(float(patterns.get('conversion_to_offer') or 0) * 100)}%"
    )


def _render_repeated_gaps(repeated_gaps: list[dict[str, Any]]) -> None:
    st.markdown("### Repeated Gap Analysis")
    if not repeated_gaps:
        st.success("No recurring gaps detected yet.")
        return

    rows = []
    for item in repeated_gaps[:10]:
        rows.append(
            {
                "Gap": item.get("keyword") or "—",
                "Count": item.get("count", 0),
                "Severity": item.get("severity") or "—",
                "Examples": ", ".join(item.get("example_vacancy_titles") or []) or "—",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_evidence_coverage_trends(trends: dict[str, Any] | None) -> None:
    trends = trends or {}
    st.markdown("### Evidence Coverage Trends")

    most_reusable = trends.get("most_reusable_evidence") or []
    unused = trends.get("unused_evidence") or []
    weak_clusters = trends.get("weak_evidence_clusters") or []

    col_reusable, col_unused, col_clusters = st.columns(3)

    with col_reusable:
        st.metric("Most reusable", len(most_reusable))
    with col_unused:
        st.metric("Unused", len(unused))
    with col_clusters:
        st.metric("Weak clusters", len(weak_clusters))

    if most_reusable:
        st.markdown("#### Most reusable evidence")
        for item in most_reusable[:5]:
            st.markdown(f"- **{item.get('title') or 'Evidence'}**")
            st.caption(
                f"usage={_format_count(item.get('usage_count'))} · "
                f"strength={item.get('evidence_strength') or '—'} · "
                f"fact_status={item.get('fact_status') or '—'}"
            )
            if item.get("reason"):
                st.caption(item.get("reason"))

    if unused:
        st.markdown("#### Unused evidence")
        for item in unused[:5]:
            st.markdown(f"- {item.get('title') or 'Evidence'}")

    if weak_clusters:
        st.markdown("#### Weak evidence clusters")
        for item in weak_clusters[:5]:
            examples = ", ".join(item.get("example_evidence_titles") or []) or "—"
            st.markdown(
                f"- {item.get('skill') or '—'}"
                f" ({item.get('count', 0)})"
            )
            st.caption(f"Examples: {examples}")


def _render_recommendations(recommendations: list[dict[str, Any]]) -> None:
    st.markdown("### Strategic Recommendations")
    if not recommendations:
        st.success("No strategic recommendations right now.")
        return

    for item in recommendations:
        priority = str(item.get("priority") or "low").lower()
        title = str(item.get("title") or "Recommendation")
        message = str(item.get("message") or "")
        if priority == "high":
            st.error(title)
        elif priority == "medium":
            st.warning(title)
        else:
            st.info(title)
        if message:
            st.write(message)


def render_career_strategy_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
) -> None:
    st.header("Career Strategy")
    st.caption(
        "Deterministic operational guidance: recurring gaps, evidence coverage trends, "
        "application patterns, and concrete next steps."
    )

    try:
        summary = client.get_career_insights(token=token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            st.info("Career insights are available after you have profile, vacancy, evidence, and application data.")
        else:
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

    if not isinstance(summary, dict):
        st.error("Backend returned an unexpected career insights payload")
        st.json(summary)
        return

    col_gaps, col_evidence, col_apps = st.columns(3)
    with col_gaps:
        st.metric("Recurring gaps", len(summary.get("repeated_gaps") or []))
    with col_evidence:
        coverage = summary.get("evidence_coverage_trends") or {}
        st.metric("Reusable evidence", len(coverage.get("most_reusable_evidence") or []))
    with col_apps:
        patterns = summary.get("application_patterns") or {}
        st.metric("Applications sent", patterns.get("applications_sent", 0))

    _render_repeated_gaps(summary.get("repeated_gaps") or [])
    st.divider()
    _render_evidence_coverage_trends(summary.get("evidence_coverage_trends") or {})
    st.divider()
    _render_application_patterns(summary.get("application_patterns") or {})
    st.divider()
    _render_recommendations(summary.get("strategic_recommendations") or [])

    sample = summary.get("vacancy_intelligence_sample") or []
    if sample:
        with st.expander("Vacancy intelligence sample", expanded=False):
            st.json(sample)

    with st.expander("Raw JSON", expanded=False):
        st.json(summary)
