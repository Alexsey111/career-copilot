# app\services\document_builders.py

from __future__ import annotations

from typing import Any

from app.schemas.json_contracts import ClaimItem, WarningItem
from app.domain.document_models import SelectedAchievement
from app.services.document_validation_service import validate_document_content
from app.services.document_serialization import to_jsonable, serialize_achievement
from app.domain.trace_models import GenerationTrace
from app.services.trace_serialization import serialize_trace


def build_resume_content(
    *,
    candidate: dict[str, Any],
    target_vacancy: dict[str, Any],
    draft_mode: str,
    fit_summary: dict[str, Any],
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
    based_on_analysis_id: Any,
    confidence: float,
    generation_prompt_version: str | None,
    generated_at: str,
    trace: GenerationTrace | None = None,
) -> dict:
    payload = {
        "document_kind": "resume",
        "draft_mode": draft_mode,
        "candidate": to_jsonable(candidate),
        "target_vacancy": to_jsonable(target_vacancy),
        "sections": {
            "fit_summary": fit_summary,
            "summary_bullets": summary_bullets,
            "skills": skills,
            "experience": to_jsonable(experience),
            "selected_achievements": [
                serialize_achievement(item)
                for item in selected_achievements
            ],
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
            "based_on_analysis_id": based_on_analysis_id,
            "confidence": confidence,
            "generation_prompt_version": generation_prompt_version,
            "generated_at": generated_at,
            "warnings": [],
            "generation_trace": serialize_trace(trace) if trace else {},
        },
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
    based_on_analysis_id: Any,
    confidence: float,
    generation_prompt_version: str | None,
    generated_at: str,
    trace: GenerationTrace | None = None,
) -> dict:
    payload = {
        "document_kind": "cover_letter",
        "draft_mode": draft_mode,
        "candidate": to_jsonable(candidate),
        "target_vacancy": to_jsonable(target_vacancy),
        "sections": {
            "opening": opening,
            "relevance_paragraph": relevance_paragraph,
            "closing": closing,
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "matched_requirements": to_jsonable(matched_requirements),
            "gap_requirements": to_jsonable(gap_requirements),
            "selected_achievements": [
                serialize_achievement(item)
                for item in selected_achievements
            ],
            "claims_needing_confirmation": to_jsonable(claims_needing_confirmation),
            "warnings": to_jsonable(warnings),
        },
        "meta": {
            "source": source,
            "based_on_achievements": based_on_achievements,
            "based_on_analysis_id": based_on_analysis_id,
            "confidence": confidence,
            "generation_prompt_version": generation_prompt_version,
            "generated_at": generated_at,
            "warnings": [],
            "generation_trace": serialize_trace(trace) if trace else {},
        },
    }

    validated = validate_document_content(
        document_kind="cover_letter",
        payload=payload,
    )

    return validated.model_dump(mode="json")
