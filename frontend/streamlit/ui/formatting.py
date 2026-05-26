from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from ui.labels import (
    APPLICATION_OUTCOME_LABELS,
    APPLICATION_STATUS_LABELS,
    CONFIDENCE_LEVEL_LABELS,
    CONFIDENCE_TONES,
    DEMO_COMPANY_LABELS,
    DEMO_LOCATION_LABELS,
    DEMO_VACANCY_TITLE_LABELS,
    DOCUMENT_KIND_LABELS,
    RISK_LEVEL_TONES,
    SEVERITY_TONES,
    TRUST_PANEL_TEXT_REPLACEMENTS,
)


def format_application_status(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_STATUS_LABELS.get(value, value)


def format_optional_datetime(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ")[:19]


def format_application_outcome(value: str | None) -> str:
    if not value:
        return "—"
    return APPLICATION_OUTCOME_LABELS.get(value, value)


def format_vacancy_title(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_VACANCY_TITLE_LABELS.get(value, value)


def format_vacancy_company(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_COMPANY_LABELS.get(value, value)


def format_vacancy_location(value: str | None) -> str:
    if not value:
        return "—"
    return DEMO_LOCATION_LABELS.get(value, value)


def _format_label(value: str | None, labels: dict[str, str]) -> str:
    if not value:
        return "—"
    normalized = str(value).strip().lower()
    return labels.get(normalized, value)


def _translate_trust_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return TRUST_PANEL_TEXT_REPLACEMENTS.get(text, text)


def _format_confidence_value(provenance_summary: dict[str, Any] | None) -> str:
    provenance_summary = provenance_summary or {}
    confidence_level = str(provenance_summary.get("confidence_level") or "").strip().lower()
    confidence = provenance_summary.get("confidence")

    if confidence_level and confidence is not None:
        level_label = CONFIDENCE_LEVEL_LABELS.get(confidence_level, confidence_level)
        try:
            return f"{level_label} ({round(float(confidence), 2)})"
        except (TypeError, ValueError):
            return f"{level_label} ({confidence})"

    if confidence_level:
        return CONFIDENCE_LEVEL_LABELS.get(confidence_level, confidence_level)

    if confidence is not None:
        try:
            return f"{round(float(confidence), 2)}"
        except (TypeError, ValueError):
            return str(confidence)

    return "—"


def _render_badge(label: str, *, tone: str = "neutral") -> None:
    colors = SEVERITY_TONES.get(tone, SEVERITY_TONES["neutral"])
    st.markdown(
        (
            "<span style='display:inline-block;"
            "padding:0.25rem 0.65rem;"
            "border-radius:999px;"
            f"background:{colors['bg']};"
            f"color:{colors['fg']};"
            "font-size:0.78rem;"
            "font-weight:700;"
            "line-height:1.2;"
            "margin-right:0.35rem;"
            "margin-bottom:0.35rem;'>"
            f"{escape(label)}"
            "</span>"
        ),
        unsafe_allow_html=True,
    )


def _render_inline_badges(badges: list[tuple[str, str]]) -> None:
    if not badges:
        return
    columns = st.columns(len(badges))
    for column, (label, tone) in zip(columns, badges, strict=False):
        with column:
            _render_badge(label, tone=tone)


def _confidence_badge_tone(confidence_level: str | None) -> str:
    if not confidence_level:
        return "neutral"
    return CONFIDENCE_TONES.get(str(confidence_level).strip().lower(), "neutral")


def _risk_badge_tone(risk_level: str | None) -> str:
    if not risk_level:
        return "neutral"
    return RISK_LEVEL_TONES.get(str(risk_level).strip().lower(), "neutral")


def _action_badge_tone(severity: str | None) -> str:
    if not severity:
        return "neutral"
    normalized = str(severity).strip().lower()
    return normalized if normalized in SEVERITY_TONES else "neutral"


def _render_trust_panel_list(title: str, items: list[str]) -> None:
    st.markdown(f"**{_translate_trust_text(title)}**")
    if not items:
        st.caption(_translate_trust_text("No items."))
        return
    for item in items:
        st.markdown(f"- {_translate_trust_text(item)}")


def _humanize_document_kind_for_trust_panel(document_kind: str | None) -> str:
    if not document_kind:
        return "Документ"
    normalized = str(document_kind).strip().lower()
    return DOCUMENT_KIND_LABELS.get(normalized, document_kind)
