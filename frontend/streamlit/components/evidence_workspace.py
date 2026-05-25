# frontend\streamlit\components\evidence_workspace.py

from __future__ import annotations

from typing import Any

import re
import httpx
import streamlit as st

from api_client import CareerCopilotApiClient


def _format_count(value: Any) -> str:
    try:
        return str(int(value or 0))
    except (TypeError, ValueError):
        return "0"


def _skill_labels(value: Any) -> str:
    skills = value or []
    if not isinstance(skills, list):
        return "—"
    normalized = [str(item).strip() for item in skills if str(item).strip()]
    return ", ".join(normalized) if normalized else "—"


def _format_short_uuid(value: Any) -> str:
    text = str(value or "").strip()
    return text[:8] if text else "—"


def _render_metrics(snippets: list[dict[str, Any]]) -> None:
    strength_counts = {"strong": 0, "medium": 0, "weak": 0}
    fact_counts = {"confirmed": 0, "partial": 0, "unverified": 0}

    for item in snippets:
        strength = str(item.get("evidence_strength") or "weak").strip().lower()
        fact_status = str(item.get("fact_status") or "unverified").strip().lower()
        if strength in strength_counts:
            strength_counts[strength] += 1
        if fact_status in fact_counts:
            fact_counts[fact_status] += 1

    col_total, col_strong, col_medium, col_weak, col_confirmed, col_unverified = st.columns(6)

    with col_total:
        st.metric("Всего", len(snippets))
    with col_strong:
        st.metric("Сильные", strength_counts["strong"])
    with col_medium:
        st.metric("Средние", strength_counts["medium"])
    with col_weak:
        st.metric("Слабые", strength_counts["weak"])
    with col_confirmed:
        st.metric("Подтверждённые", fact_counts["confirmed"])
    with col_unverified:
        st.metric("Неподтверждённые", fact_counts["unverified"])


def _local_insights(snippets: list[dict[str, Any]]) -> dict[str, Any]:
    def _resolve_star_summary(item: dict[str, Any]) -> dict[str, Any]:
        star_summary = item.get("star_summary") or item.get("star_summary_json")
        if isinstance(star_summary, dict):
            return star_summary
        return {}

    def _has_metrics(item: dict[str, Any]) -> bool:
        combined = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("snippet_text") or ""),
                str(_resolve_star_summary(item).get("situation") or ""),
                str(_resolve_star_summary(item).get("task") or ""),
                str(_resolve_star_summary(item).get("action") or ""),
                str(_resolve_star_summary(item).get("result") or ""),
            ]
        ).lower()
        metric_patterns = [
            r"\b\d+(?:\.\d+)?%",
            r"\$\s*\d",
            r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds|min|mins|minutes|hr|hrs|hours|day|days|week|weeks|month|months|user|users|customer|customers|request|requests|ticket|tickets|issue|issues|call|calls)\b",
        ]
        metric_keywords = (
            "metric",
            "metrics",
            "kpi",
            "latency",
            "throughput",
            "revenue",
            "cost",
            "conversion",
            "retention",
            "growth",
            "accuracy",
            "error rate",
            "performance",
            "time to",
            "sla",
            "slo",
        )
        if any(re.search(pattern, combined) for pattern in metric_patterns):
            return True
        return any(keyword in combined for keyword in metric_keywords)

    recommendations: list[dict[str, Any]] = []
    counts = {
        "weak_evidence_count": 0,
        "missing_metrics_count": 0,
        "missing_star_fields_count": 0,
        "unused_evidence_count": 0,
        "overused_evidence_count": 0,
        "unverified_evidence_count": 0,
    }

    for item in snippets:
        strength = str(item.get("evidence_strength") or "weak").strip().lower()
        fact_status = str(item.get("fact_status") or "unverified").strip().lower()
        usage_count = int(item.get("usage_count") or 0)
        star_summary = _resolve_star_summary(item)
        complete_star = all(str(star_summary.get(field) or "").strip() for field in ("situation", "task", "action", "result"))

        if strength == "weak":
            counts["weak_evidence_count"] += 1
            recommendations.append(
                {
                    "type": "weak_evidence",
                    "evidence_id": item.get("id"),
                    "title": item.get("title") or "Evidence snippet",
                    "message": "Evidence strength is weak. Review the wording, metrics, or supporting context before reuse.",
                    "severity": "warning",
                }
            )

        if not _has_metrics(item):
            counts["missing_metrics_count"] += 1
            recommendations.append(
                {
                    "type": "missing_metric",
                    "evidence_id": item.get("id"),
                    "title": item.get("title") or "Evidence snippet",
                    "message": "No measurable metrics were detected. Add concrete numbers or outcome signals if they exist.",
                    "severity": "warning",
                }
            )

        if not complete_star:
            counts["missing_star_fields_count"] += 1
            recommendations.append(
                {
                    "type": "incomplete_star",
                    "evidence_id": item.get("id"),
                    "title": item.get("title") or "Evidence snippet",
                    "message": "STAR coverage is incomplete. Fill in the missing Situation, Task, Action, or Result fields.",
                    "severity": "warning",
                }
            )

        if usage_count == 0:
            counts["unused_evidence_count"] += 1
            recommendations.append(
                {
                    "type": "unused_evidence",
                    "evidence_id": item.get("id"),
                    "title": item.get("title") or "Evidence snippet",
                    "message": "This evidence has not been used yet. Consider it for upcoming resume or interview drafts.",
                    "severity": "info",
                }
            )

        if usage_count >= 3:
            counts["overused_evidence_count"] += 1
            recommendations.append(
                {
                    "type": "overused_evidence",
                    "evidence_id": item.get("id"),
                    "title": item.get("title") or "Evidence snippet",
                    "message": "This evidence is reused often. Consider rotating in alternative evidence to avoid repetition.",
                    "severity": "warning",
                }
            )

        if fact_status != "confirmed":
            counts["unverified_evidence_count"] += 1
            recommendations.append(
                {
                    "type": "unverified_evidence",
                    "evidence_id": item.get("id"),
                    "title": item.get("title") or "Evidence snippet",
                    "message": "This fact is not confirmed yet. Keep it out of strong evidence paths until reviewed.",
                    "severity": "warning",
                }
            )

    return {**counts, "recommendations": recommendations}


def _render_insights_section(
    insights: dict[str, Any] | None,
    snippets: list[dict[str, Any]],
) -> None:
    st.markdown("### Инсайты по качеству доказательств")
    st.caption("Детерминированные сигналы качества для слоя переиспользуемых доказательств.")

    data = insights if isinstance(insights, dict) else _local_insights(snippets)

    col_total, col_weak, col_metrics = st.columns(3)
    col_star, col_unused, col_overused = st.columns(3)
    col_unverified, col_recommendations, col_spacer = st.columns([1, 1, 1])

    with col_total:
        st.metric("Всего сниппетов", len(snippets))
    with col_weak:
        st.metric("Слабые доказательства", data.get("weak_evidence_count", 0))
    with col_metrics:
        st.metric("Нет метрик", data.get("missing_metrics_count", 0))

    with col_star:
        st.metric("Неполный STAR", data.get("missing_star_fields_count", 0))
    with col_unused:
        st.metric("Не использовались", data.get("unused_evidence_count", 0))
    with col_overused:
        st.metric("Слишком часто", data.get("overused_evidence_count", 0))

    with col_unverified:
        st.metric("Требуют подтверждения", data.get("unverified_evidence_count", 0))

    recommendations = data.get("recommendations") or []
    if not isinstance(recommendations, list):
        recommendations = []

    st.markdown("#### Нуждаются во внимании")
    if recommendations:
        rows = []
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "Type": item.get("type") or "—",
                    "Severity": item.get("severity") or "—",
                    "Title": item.get("title") or "—",
                    "Message": item.get("message") or "—",
                    "Evidence": _format_short_uuid(item.get("evidence_id")),
                }
            )

        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("Пока нет рекомендаций к действию.")
    else:
        st.success("Сейчас ни одно доказательство не требует внимания.")


def _build_rows(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in snippets:
        rows.append(
            {
                "title": item.get("title") or "—",
                "strength": item.get("evidence_strength") or "—",
                "fact_status": item.get("fact_status") or "—",
                "skills": _skill_labels(item.get("skills") or item.get("skills_json")),
                "usage": _format_count(item.get("usage_count")),
                "documents": _format_count(item.get("used_in_documents_count")),
                "interviews": _format_count(item.get("used_in_interviews_count")),
            }
        )
    return rows


def _render_detail_panel(snippet: dict[str, Any], usages: list[dict[str, Any]]) -> None:
    st.markdown("### Детали доказательства")
    st.write(snippet.get("title") or "—")

    col_source, col_strength, col_fact, col_usage = st.columns(4)
    with col_source:
        st.metric("Источник", snippet.get("source_type") or "—")
    with col_strength:
        st.metric("Сила", snippet.get("evidence_strength") or "—")
    with col_fact:
        st.metric("Статус факта", snippet.get("fact_status") or "—")
    with col_usage:
        st.metric("Использований", _format_count(snippet.get("usage_count")))

    st.markdown("#### Текст сниппета")
    st.text_area(
        "Сниппет",
        value=str(snippet.get("snippet_text") or ""),
        height=180,
        disabled=True,
        label_visibility="collapsed",
    )

    star_summary = snippet.get("star_summary") or snippet.get("star_summary_json") or {}
    st.markdown("#### STAR-сводка")
    if isinstance(star_summary, dict) and any(str(value or "").strip() for value in star_summary.values()):
        st.json(star_summary)
    else:
        st.caption("STAR-сводка недоступна.")

    col_docs, col_interviews = st.columns(2)
    with col_docs:
        st.metric("Использовано в документах", _format_count(snippet.get("used_in_documents_count")))
    with col_interviews:
        st.metric("Использовано в интервью", _format_count(snippet.get("used_in_interviews_count")))

    if usages:
        with st.expander("Недавние использования", expanded=False):
            rows = []
            for usage in usages[:20]:
                rows.append(
                    {
                        "usage_type": usage.get("usage_type") or "—",
                        "target_type": usage.get("target_type") or "—",
                        "target_id": usage.get("target_id") or "—",
                        "note": usage.get("note") or "—",
                        "created_at": usage.get("created_at") or "—",
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)


def render_evidence_workspace_tab(
    client: CareerCopilotApiClient,
    *,
    token: str | None = None,
) -> None:
    st.header("Источники доказательств")
    st.caption(
        "Каталог доказательств только для чтения: документы, cover letters, интервью "
        "и будущие рекомендации."
    )

    if not token:
        st.warning("Войдите, чтобы открыть источники доказательств.")
        return

    try:
        snippets = client.list_evidence_snippets(token=token)
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

    if not isinstance(snippets, list):
        st.error("Backend вернул неожиданный список сниппетов")
        st.json(snippets)
        return

    snippet_rows: list[dict[str, Any]] = []
    for item in snippets:
        if isinstance(item, dict):
            snippet_rows.append(item)

    try:
        insights = client.get_evidence_insights(token=token)
    except httpx.HTTPStatusError as exc:
        st.warning(f"Insights endpoint вернул HTTP {exc.response.status_code}. Показываю локальные сигналы fallback.")
        insights = None
    except httpx.RequestError as exc:
        st.warning("Не удалось подключиться к insights endpoint. Показываю локальные сигналы fallback.")
        st.code(str(exc))
        insights = None
    except ValueError as exc:
        st.warning("Insights endpoint вернул неожиданный ответ. Показываю локальные сигналы fallback.")
        st.code(str(exc))
        insights = None

    _render_insights_section(insights, snippet_rows)

    _render_metrics(snippet_rows)

    if not snippet_rows:
        st.info("Сниппеты доказательств пока недоступны.")
        return

    st.markdown("### Каталог доказательств")
    st.dataframe(_build_rows(snippet_rows), width="stretch", hide_index=True)

    snippet_ids = [str(item.get("id") or "").strip() for item in snippet_rows if item.get("id")]
    if not snippet_ids:
        st.warning("Не найдено валидных ID сниппетов доказательств.")
        return

    snippets_by_id = {str(item.get("id")): item for item in snippet_rows if item.get("id")}
    selected_snippet_id = st.selectbox(
        "Выберите сниппет доказательства",
        options=snippet_ids,
        format_func=lambda value: (
            f"{snippets_by_id[value].get('title') or 'Evidence'} "
            f"· {snippets_by_id[value].get('evidence_strength') or '—'} "
            f"· {snippets_by_id[value].get('fact_status') or '—'} "
            f"· {value[:8]}"
        ),
    )

    if not selected_snippet_id:
        return

    try:
        snippet = client.get_evidence_snippet(selected_snippet_id, token=token)
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

    if not isinstance(snippet, dict):
        st.error("Backend вернул неожиданный payload сниппета")
        st.json(snippet)
        return

    try:
        usages = client.list_evidence_usages(token=token)
    except Exception:
        usages = []

    relevant_usages = []
    if isinstance(usages, list):
        for usage in usages:
            if str(usage.get("evidence_snippet_id") or "") == selected_snippet_id:
                relevant_usages.append(usage)

    _render_detail_panel(snippet, relevant_usages)
