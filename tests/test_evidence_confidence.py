from __future__ import annotations

from app.domain.evidence_confidence import (
    EvidenceConfidenceLevel,
    aggregate_evidence_confidence,
    assess_evidence_confidence,
)


def test_assess_evidence_confidence_maps_confirmed_strong_to_high() -> None:
    assessment = assess_evidence_confidence(
        {
            "fact_status": "confirmed",
            "evidence_strength": "strong",
            "star_summary": {
                "situation": "S",
                "task": "T",
                "action": "A",
                "result": "R",
            },
        }
    )

    assert assessment.confidence_level == EvidenceConfidenceLevel.HIGH
    assert assessment.confidence >= 0.9
    assert assessment.requires_human_review is True


def test_assess_evidence_confidence_maps_partial_to_low() -> None:
    assessment = assess_evidence_confidence(
        {
            "fact_status": "partial",
            "evidence_strength": "medium",
        }
    )

    assert assessment.confidence_level == EvidenceConfidenceLevel.LOW
    assert assessment.confidence < 0.5
    assert assessment.requires_human_review is True


def test_assess_evidence_confidence_maps_gap_risk_to_needs_review() -> None:
    assessment = assess_evidence_confidence(
        {
            "fact_status": "inferred_needs_review",
            "source_type": "gap",
        }
    )

    assert assessment.confidence_level == EvidenceConfidenceLevel.NEEDS_REVIEW
    assert assessment.requires_human_review is True


def test_aggregate_evidence_confidence_maps_mixed_items_to_medium() -> None:
    assessment = aggregate_evidence_confidence(
        [
            {
                "fact_status": "confirmed",
                "evidence_strength": "strong",
                "star_summary": {
                    "situation": "S",
                    "task": "T",
                    "action": "A",
                    "result": "R",
                },
            },
            {
                "fact_status": "confirmed",
                "evidence_strength": "medium",
                "star_summary": {
                    "situation": "S",
                },
            },
        ]
    )

    assert assessment.confidence_level in {
        EvidenceConfidenceLevel.HIGH,
        EvidenceConfidenceLevel.MEDIUM,
    }
    assert assessment.requires_human_review is True
