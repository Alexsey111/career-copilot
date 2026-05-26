from __future__ import annotations

from typing import Any

import streamlit as st


def init_session_state() -> None:
    if "source_file" not in st.session_state:
        st.session_state.source_file = None
    if "resume_source_mode" not in st.session_state:
        st.session_state.resume_source_mode = "Загрузить новое"
    if "resume_import" not in st.session_state:
        st.session_state.resume_import = None
    if "structured_profile" not in st.session_state:
        st.session_state.structured_profile = None
    if "achievements" not in st.session_state:
        st.session_state.achievements = None
    if "vacancy" not in st.session_state:
        st.session_state.vacancy = None
    if "vacancy_analysis" not in st.session_state:
        st.session_state.vacancy_analysis = None
    if "generated_resume" not in st.session_state:
        st.session_state.generated_resume = None
    if "generated_cover_letter" not in st.session_state:
        st.session_state.generated_cover_letter = None
    if "approved_resume" not in st.session_state:
        st.session_state.approved_resume = None
    if "approved_cover_letter" not in st.session_state:
        st.session_state.approved_cover_letter = None
    if "application" not in st.session_state:
        st.session_state.application = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "trust_panel_entity_type" not in st.session_state:
        st.session_state.trust_panel_entity_type = "document"
    if "trust_panel_document_id" not in st.session_state:
        st.session_state.trust_panel_document_id = None
    if "trust_panel_interview_prep_id" not in st.session_state:
        st.session_state.trust_panel_interview_prep_id = None


def _reset_downstream_resume_state() -> None:
    st.session_state.resume_import = None
    st.session_state.structured_profile = None
    st.session_state.achievements = None
    st.session_state.vacancy = None
    st.session_state.vacancy_analysis = None
    st.session_state.generated_resume = None
    st.session_state.generated_cover_letter = None
    st.session_state.approved_resume = None
    st.session_state.approved_cover_letter = None
    st.session_state.application = None


def _store_intake_result_as_resume_import(result: dict[str, Any]) -> None:
    st.session_state.resume_import = {
        "profile_id": result.get("profile_id"),
        "source_file_id": result.get("source_file_id"),
        "extraction_id": result.get("extraction_id"),
        "status": result.get("status") or "completed",
        "detected_format": result.get("source") or "guided_intake",
        "text_length": len(str(result.get("raw_text_preview") or "")),
        "text_preview": result.get("raw_text_preview") or "",
    }
    st.session_state.structured_profile = {
        "profile_id": result.get("profile_id"),
        "extraction_id": result.get("extraction_id"),
        "full_name": result.get("full_name"),
        "headline": ", ".join(result.get("target_roles") or []),
        "location": result.get("location"),
        "target_roles": result.get("target_roles") or [],
        "experience_count": result.get("experience_count") or 0,
        "project_count": result.get("project_count") or 0,
        "evidence_snippet_count": result.get("evidence_snippet_count") or 0,
        "technologies": result.get("technologies") or [],
        "ai_tools": result.get("ai_tools") or [],
        "automation_tools": result.get("automation_tools") or [],
        "warnings": [],
    }


def _split_csv(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]
