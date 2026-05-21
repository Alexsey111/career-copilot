from __future__ import annotations

from app.services.review_summary_service import ReviewSummaryService


def test_review_summary_recommendations_include_missing_evidence_action() -> None:
    service = ReviewSummaryService()

    actions = service._recommended_actions(  # noqa: SLF001
        entity_type="document",
        ready=False,
        blockers=[],
        warnings=[],
        claims_requiring_confirmation=[],
        gap_risk_items=[],
        provenance_summary={
            "confidence": 0.45,
            "confidence_level": "low",
            "requires_human_review": True,
            "document_id": "doc-1",
        },
        selected_evidence=[],
    )

    action_codes = {item["code"] for item in actions}
    assert "review_low_confidence" in action_codes
    assert "attach_missing_evidence" in action_codes
