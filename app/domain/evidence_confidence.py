# app/domain/evidence_confidence.py

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from app.domain.evidence import (
    EvidenceFactStatus,
    EvidenceStrengthLevel,
    STAREvidenceSummary,
)


class EvidenceConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEEDS_REVIEW = "needs_review"


@dataclass(slots=True)
class EvidenceConfidenceAssessment:
    confidence: float
    confidence_level: EvidenceConfidenceLevel
    requires_human_review: bool
    fact_status: str
    evidence_strength: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "requires_human_review": self.requires_human_review,
            "fact_status": self.fact_status,
            "evidence_strength": self.evidence_strength,
            "reason": self.reason,
        }


def assess_evidence_confidence(
    evidence: Mapping[str, Any] | None = None,
    *,
    fact_status: str | None = None,
    evidence_strength: str | None = None,
    source_type: str | None = None,
    gap_risk: bool = False,
    star_summary: Mapping[str, Any] | STAREvidenceSummary | None = None,
) -> EvidenceConfidenceAssessment:
    payload = dict(evidence or {})
    normalized_fact_status = _normalize_fact_status(
        fact_status if fact_status is not None else payload.get("fact_status")
    )
    normalized_strength = _normalize_strength(
        evidence_strength if evidence_strength is not None else payload.get("evidence_strength")
    )
    normalized_source_type = str(source_type if source_type is not None else payload.get("source_type") or "").strip().lower()
    normalized_star = _resolve_star_summary(star_summary if star_summary is not None else payload.get("star_summary"))
    gap_risk = gap_risk or normalized_source_type == "gap" or normalized_fact_status == "inferred_needs_review"

    if gap_risk:
        return EvidenceConfidenceAssessment(
            confidence=0.2,
            confidence_level=EvidenceConfidenceLevel.NEEDS_REVIEW,
            requires_human_review=True,
            fact_status=normalized_fact_status or "inferred_needs_review",
            evidence_strength=normalized_strength or EvidenceStrengthLevel.WEAK.value,
            reason="gap-risk requires human review",
        )

    if normalized_fact_status == EvidenceFactStatus.CONFIRMED:
        if normalized_strength == EvidenceStrengthLevel.STRONG.value and normalized_star.is_complete:
            return EvidenceConfidenceAssessment(
                confidence=0.95,
                confidence_level=EvidenceConfidenceLevel.HIGH,
                requires_human_review=True,
                fact_status=normalized_fact_status,
                evidence_strength=normalized_strength,
                reason="confirmed strong evidence with complete STAR",
            )
        if normalized_strength == EvidenceStrengthLevel.STRONG.value:
            return EvidenceConfidenceAssessment(
                confidence=0.9,
                confidence_level=EvidenceConfidenceLevel.HIGH,
                requires_human_review=True,
                fact_status=normalized_fact_status,
                evidence_strength=normalized_strength,
                reason="confirmed strong evidence",
            )
        if normalized_strength == EvidenceStrengthLevel.MEDIUM.value or normalized_star.has_partial_content:
            return EvidenceConfidenceAssessment(
                confidence=0.68,
                confidence_level=EvidenceConfidenceLevel.MEDIUM,
                requires_human_review=True,
                fact_status=normalized_fact_status,
                evidence_strength=normalized_strength,
                reason="confirmed evidence with partial STAR or medium strength",
            )
        return EvidenceConfidenceAssessment(
            confidence=0.45,
            confidence_level=EvidenceConfidenceLevel.LOW,
            requires_human_review=True,
            fact_status=normalized_fact_status,
            evidence_strength=normalized_strength,
            reason="confirmed evidence but weak supporting signals",
        )

    if normalized_fact_status == EvidenceFactStatus.PARTIAL:
        if normalized_strength == EvidenceStrengthLevel.STRONG.value and normalized_star.has_partial_content:
            confidence = 0.42
        elif normalized_strength == EvidenceStrengthLevel.MEDIUM.value:
            confidence = 0.35
        else:
            confidence = 0.3
        return EvidenceConfidenceAssessment(
            confidence=confidence,
            confidence_level=EvidenceConfidenceLevel.LOW,
            requires_human_review=True,
            fact_status=normalized_fact_status,
            evidence_strength=normalized_strength,
            reason="partial evidence requires human review",
        )

    return EvidenceConfidenceAssessment(
        confidence=0.2,
        confidence_level=EvidenceConfidenceLevel.LOW,
        requires_human_review=True,
        fact_status=normalized_fact_status or EvidenceFactStatus.UNVERIFIED,
        evidence_strength=normalized_strength or EvidenceStrengthLevel.WEAK.value,
        reason="unverified evidence requires human review",
    )


def aggregate_evidence_confidence(
    items: Sequence[Mapping[str, Any] | EvidenceConfidenceAssessment] | None,
    *,
    gap_risk: bool = False,
) -> EvidenceConfidenceAssessment:
    normalized_items: list[EvidenceConfidenceAssessment] = []
    for item in items or []:
        if isinstance(item, EvidenceConfidenceAssessment):
            normalized_items.append(item)
        else:
            normalized_items.append(assess_evidence_confidence(item))

    if gap_risk or any(item.confidence_level == EvidenceConfidenceLevel.NEEDS_REVIEW for item in normalized_items):
        return EvidenceConfidenceAssessment(
            confidence=0.2 if normalized_items else 0.15,
            confidence_level=EvidenceConfidenceLevel.NEEDS_REVIEW,
            requires_human_review=True,
            fact_status="inferred_needs_review",
            evidence_strength=EvidenceStrengthLevel.WEAK.value,
            reason="gap-risk requires human review",
        )

    if not normalized_items:
        return EvidenceConfidenceAssessment(
            confidence=0.2,
            confidence_level=EvidenceConfidenceLevel.LOW,
            requires_human_review=True,
            fact_status=EvidenceFactStatus.UNVERIFIED,
            evidence_strength=EvidenceStrengthLevel.WEAK.value,
            reason="no evidence provided",
        )

    average_confidence = round(
        sum(item.confidence for item in normalized_items) / len(normalized_items),
        2,
    )

    if average_confidence >= 0.8:
        level = EvidenceConfidenceLevel.HIGH
    elif average_confidence >= 0.55:
        level = EvidenceConfidenceLevel.MEDIUM
    else:
        level = EvidenceConfidenceLevel.LOW

    strongest = max(normalized_items, key=lambda item: item.confidence)
    return EvidenceConfidenceAssessment(
        confidence=average_confidence,
        confidence_level=level,
        requires_human_review=True,
        fact_status=strongest.fact_status,
        evidence_strength=strongest.evidence_strength,
        reason=f"aggregate confidence from {len(normalized_items)} evidence items",
    )


def _normalize_fact_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == EvidenceFactStatus.CONFIRMED:
        return EvidenceFactStatus.CONFIRMED
    if normalized in {EvidenceFactStatus.PARTIAL, "needs_confirmation", "pending"}:
        return EvidenceFactStatus.PARTIAL
    if normalized == "inferred_needs_review":
        return "inferred_needs_review"
    return EvidenceFactStatus.UNVERIFIED


def _normalize_strength(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == EvidenceStrengthLevel.STRONG:
        return EvidenceStrengthLevel.STRONG
    if normalized == EvidenceStrengthLevel.MEDIUM:
        return EvidenceStrengthLevel.MEDIUM
    return EvidenceStrengthLevel.WEAK


@dataclass(slots=True)
class _StarState:
    is_complete: bool
    has_partial_content: bool


def _resolve_star_summary(value: Any) -> _StarState:
    if isinstance(value, STAREvidenceSummary):
        return _StarState(
            is_complete=value.is_complete,
            has_partial_content=any(
                str(field or "").strip()
                for field in (value.situation, value.task, value.action, value.result)
            ),
        )
    if isinstance(value, Mapping):
        summary = STAREvidenceSummary(
            situation=str(value.get("situation") or "").strip() or None,
            task=str(value.get("task") or "").strip() or None,
            action=str(value.get("action") or "").strip() or None,
            result=str(value.get("result") or "").strip() or None,
        )
        return _StarState(
            is_complete=summary.is_complete,
            has_partial_content=any(
                str(field or "").strip()
                for field in (summary.situation, summary.task, summary.action, summary.result)
            ),
        )
    return _StarState(is_complete=False, has_partial_content=False)
