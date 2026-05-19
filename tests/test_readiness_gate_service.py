from __future__ import annotations

from types import SimpleNamespace

from app.services.readiness_gate_service import ReadinessGateService


def _build_document(
    *,
    review_status: str = "approved",
    is_active: bool = True,
    content_json: dict | None = None,
):
    return SimpleNamespace(
        review_status=review_status,
        is_active=is_active,
        content_json=content_json or {},
    )


def test_evaluate_document_readiness_ready_document():
    service = ReadinessGateService()
    document = _build_document(
        content_json={
            "sections": {
                "claims_needing_confirmation": [],
                "selected_achievements": [{"metric_text": "Improved conversion by 20%"}],
            },
            "evaluation": {
                "critical_failures": [],
                "coverage_gaps": [],
            },
            "readiness_score": {
                "overall_score": 0.82,
                "ats_score": 0.81,
            },
        }
    )

    result = service.evaluate_document_readiness(document)

    assert result.ready is True
    assert result.blockers == []
    assert result.warnings == []
    assert result.score == 0.82


def test_evaluate_document_readiness_collects_blockers():
    service = ReadinessGateService()
    document = _build_document(
        review_status="review_required",
        is_active=False,
        content_json={
            "sections": {
                "claims_needing_confirmation": [{"claim_text": "Need proof"}],
            },
            "evaluation": {
                "critical_failures": [{"code": "missing_evidence"}],
            },
        },
    )

    result = service.evaluate_document_readiness(document)

    assert result.ready is False
    assert "document review_status is not approved" in result.blockers
    assert "document has unresolved claims requiring confirmation" in result.blockers
    assert "document has unresolved critical evaluation failures" in result.blockers
    assert "document is not active" in result.blockers


def test_evaluate_document_readiness_collects_warnings():
    service = ReadinessGateService()
    document = _build_document(
        content_json={
            "sections": {
                "selected_achievements": [
                    {"metric_text": ""},
                    {"metric_text": "Reduced latency by 35%"},
                ],
            },
            "evaluation": {
                "coverage_gaps": [{"requirement": "Docker"}],
            },
            "readiness_score": {
                "overall_score": 0.74,
                "ats_score": 0.55,
            },
        }
    )

    result = service.evaluate_document_readiness(document)

    assert result.ready is True
    assert "document has coverage gaps" in result.warnings
    assert "document has low ATS score (0.55)" in result.warnings
    assert "document has achievements with missing metrics" in result.warnings
    assert result.score == 0.74


def test_evaluate_document_readiness_supports_fallback_score_sources():
    service = ReadinessGateService()
    document = _build_document(
        content_json={
            "sections": {
                "claims_needing_confirmation": [],
                "selected_achievements": [],
            },
            "evaluation": {
                "critical_failures": [],
                "ats_score": 0.76,
            },
            "meta": {
                "readiness_score": {
                    "overall_score": 0.79,
                },
            },
        }
    )

    result = service.evaluate_document_readiness(document)

    assert result.ready is True
    assert result.score == 0.79
    assert result.warnings == []
