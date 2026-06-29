# app\services\document_builders.py

from __future__ import annotations

from typing import Any

from app.schemas.json_contracts import ClaimItem, WarningItem
from app.domain.document_models import SelectedAchievement
from app.services.document_validation_service import validate_document_content
from app.services.document_serialization import to_jsonable
from app.domain.trace_models import GenerationTrace
from app.services.trace_serialization import serialize_trace


def _normalize_document_fact_status(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"confirmed", "user_provided"}:
        return "confirmed"
    if normalized in {"needs_confirmation", "partial", "pending"}:
        return "needs_confirmation"
    if normalized == "inferred":
        return "inferred"
    return "needs_confirmation"


def _normalize_fact_statuses_in_items(items: list[dict]) -> list[dict]:
    normalized_items: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["fact_status"] = _normalize_document_fact_status(
            normalized.get("fact_status")
        )
        normalized_items.append(normalized)
    return normalized_items


def build_document_provenance(
    *,
    source: str,
    generation_mode: str,
    based_on_analysis_id: Any,
    based_on_achievements: list[Any],
    selected_achievement_ids: list[Any] | None,
    selected_evidence_ids: list[Any] | None,
    evidence_selection_reason: list[dict[str, Any]] | None,
    confidence: float,
    confidence_level: str | None = None,
    generation_prompt_version: str | None,
    generated_at: str,
    requires_human_review: bool = True,
) -> dict[str, Any]:
    provenance = {
        "source": source,
        "generation_mode": generation_mode,
        "analysis_id": str(based_on_analysis_id) if based_on_analysis_id is not None else None,
        "based_on_achievements": to_jsonable(based_on_achievements),
        "selected_achievement_ids": to_jsonable(selected_achievement_ids or []),
        "selected_evidence_ids": to_jsonable(selected_evidence_ids or []),
        "evidence_selection_reason": to_jsonable(evidence_selection_reason or []),
        "confidence": confidence,
        "generation_prompt_version": generation_prompt_version,
        "generated_at": generated_at,
        "requires_human_review": requires_human_review,
    }
    if confidence_level is not None:
        provenance["confidence_level"] = confidence_level
    return provenance


def build_resume_content(
    *,
    candidate: dict[str, Any],
    target_vacancy: dict[str, Any],
    draft_mode: str,
    fit_summary: dict[str, Any],
    vacancy_fit_narrative: dict[str, Any],
    summary_bullets: list[str],
    skills: list[str],
    experience: list[dict[str, Any]],
    selected_achievements: list[SelectedAchievement],
    matched_keywords: list[str],
    missing_keywords: list[str],
    matched_requirements: list[dict[str, Any]],
    gap_requirements: list[dict[str, Any]],
    claims_needing_confirmation: list[ClaimItem],
    selection_rationale: list[dict[str, Any]],
    warnings: list[WarningItem],
    source: str,
    based_on_achievements: list[Any],
    selected_achievement_ids: list[Any] | None = None,
    based_on_analysis_id: Any,
    confidence: float,
    confidence_level: str | None = None,
    generation_prompt_version: str | None,
    generated_at: str,
    trace: GenerationTrace | None = None,
    selected_evidence_ids: list[Any] | None = None,
    evidence_selection_reason: list[dict[str, Any]] | None = None,
    vacancy_aligned_summary: str | None = None,
    vacancy_evidence_alignment: list[dict[str, Any]] | None = None,
    top_alignment_evidence: list[dict[str, Any]] | None = None,
    competency_mapping: list[dict[str, Any]] | None = None,
    relevant_to_vacancy: list[str] | None = None,
    project_sections: list[dict[str, Any]] | None = None,
    education: list[dict[str, Any]] | None = None,
    courses: list[dict[str, Any]] | None = None,
    internships: list[dict[str, Any]] | None = None,
) -> dict:
    provenance = build_document_provenance(
        source=source,
        generation_mode=draft_mode,
        based_on_analysis_id=based_on_analysis_id,
        based_on_achievements=based_on_achievements,
        selected_achievement_ids=selected_achievement_ids,
        selected_evidence_ids=selected_evidence_ids,
        evidence_selection_reason=evidence_selection_reason,
        confidence=confidence,
        confidence_level=confidence_level,
        generation_prompt_version=generation_prompt_version,
        generated_at=generated_at,
    )

    normalized_selected_achievements = _normalize_fact_statuses_in_items(
        to_jsonable(selected_achievements)
    )

    payload = {
        "document_kind": "resume",
        "draft_mode": draft_mode,
        "candidate": to_jsonable(candidate),
        "target_vacancy": to_jsonable(target_vacancy),
        "sections": {
            "fit_summary": fit_summary,
            "vacancy_fit_narrative": to_jsonable(vacancy_fit_narrative),
            "vacancy_aligned_summary": vacancy_aligned_summary,
            "vacancy_evidence_alignment": to_jsonable(vacancy_evidence_alignment or []),
            "top_alignment_evidence": to_jsonable(top_alignment_evidence or []),
            "competency_mapping": to_jsonable(competency_mapping or []),
            "relevant_to_vacancy": relevant_to_vacancy or [],
            "summary_bullets": summary_bullets,
            "skills": skills,
            "experience": to_jsonable(experience),
            "education": to_jsonable(education or []),
            "courses": to_jsonable(courses or []),
            "internships": to_jsonable(internships or []),
            "project_sections": to_jsonable(project_sections or []),
            "selected_achievements": normalized_selected_achievements,
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "matched_requirements": to_jsonable(matched_requirements),
            "gap_requirements": to_jsonable(gap_requirements),
            "claims_needing_confirmation": to_jsonable(claims_needing_confirmation),
            "selection_rationale": to_jsonable(selection_rationale),
            "warnings": to_jsonable(warnings),
        },
        "meta": {
            "source": source,
            "based_on_achievements": based_on_achievements,
            "selected_achievement_ids": to_jsonable(selected_achievement_ids or []),
            "based_on_analysis_id": based_on_analysis_id,
            "selected_evidence_ids": to_jsonable(selected_evidence_ids or []),
            "evidence_selection_reason": to_jsonable(evidence_selection_reason or []),
            "confidence": confidence,
            "generation_prompt_version": generation_prompt_version,
            "generated_at": generated_at,
            "provenance": provenance,
            "warnings": [],
            "generation_trace": serialize_trace(trace) if trace else {},
        },
        "provenance": provenance,
    }

    validated = validate_document_content(
        document_kind="resume",
        payload=payload,
    )

    return validated.model_dump(mode="json")


def build_cover_letter_content(
    *,
    candidate: dict[str, Any],
    target_vacancy: dict[str, Any],
    draft_mode: str,
    opening: str,
    relevance_paragraph: str,
    closing: str,
    matched_keywords: list[str],
    missing_keywords: list[str],
    matched_requirements: list[dict[str, Any]],
    gap_requirements: list[dict[str, Any]],
    selected_achievements: list[SelectedAchievement],
    claims_needing_confirmation: list[ClaimItem],
    warnings: list[WarningItem],
    source: str,
    based_on_achievements: list[Any],
    selected_achievement_ids: list[Any] | None = None,
    based_on_analysis_id: Any,
    confidence: float,
    confidence_level: str | None = None,
    generation_prompt_version: str | None,
    generated_at: str,
    trace: GenerationTrace | None = None,
    selected_evidence_ids: list[Any] | None = None,
    evidence_selection_reason: list[dict[str, Any]] | None = None,
    vacancy_alignment: list[dict[str, Any]] | None = None,
    evidence_relevance: list[dict[str, Any]] | None = None,
) -> dict:
    provenance = build_document_provenance(
        source=source,
        generation_mode=draft_mode,
        based_on_analysis_id=based_on_analysis_id,
        based_on_achievements=based_on_achievements,
        selected_achievement_ids=selected_achievement_ids,
        selected_evidence_ids=selected_evidence_ids,
        evidence_selection_reason=evidence_selection_reason,
        confidence=confidence,
        confidence_level=confidence_level,
        generation_prompt_version=generation_prompt_version,
        generated_at=generated_at,
    )

    normalized_selected_achievements = _normalize_fact_statuses_in_items(
        to_jsonable(selected_achievements)
    )

    payload = {
        "document_kind": "cover_letter",
        "draft_mode": draft_mode,
        "candidate": to_jsonable(candidate),
        "target_vacancy": to_jsonable(target_vacancy),
        "sections": {
            "opening": opening,
            "relevance_paragraph": relevance_paragraph,
            "closing": closing,
            "vacancy_alignment": to_jsonable(vacancy_alignment or []),
            "evidence_relevance": to_jsonable(evidence_relevance or []),
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "matched_requirements": to_jsonable(matched_requirements),
            "gap_requirements": to_jsonable(gap_requirements),
            "selected_achievements": normalized_selected_achievements,
            "claims_needing_confirmation": to_jsonable(claims_needing_confirmation),
            "warnings": to_jsonable(warnings),
        },
        "meta": {
            "source": source,
            "based_on_achievements": based_on_achievements,
            "selected_achievement_ids": to_jsonable(selected_achievement_ids or []),
            "based_on_analysis_id": based_on_analysis_id,
            "selected_evidence_ids": to_jsonable(selected_evidence_ids or []),
            "evidence_selection_reason": to_jsonable(evidence_selection_reason or []),
            "confidence": confidence,
            "generation_prompt_version": generation_prompt_version,
            "generated_at": generated_at,
            "provenance": provenance,
            "warnings": [],
            "generation_trace": serialize_trace(trace) if trace else {},
        },
        "provenance": provenance,
    }

    validated = validate_document_content(
        document_kind="cover_letter",
        payload=payload,
    )

    return validated.model_dump(mode="json")
