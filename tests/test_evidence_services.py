from __future__ import annotations

from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_selection_service import EvidenceSelectionService
from app.services.evidence_strength_service import EvidenceStrengthService


def test_extraction_builds_star_summary_and_skill_tags() -> None:
    service = EvidenceExtractionService(EvidenceStrengthService())

    snippet = service.extract_from_achievement(
        {
            "id": "ach-1",
            "title": "Reduced API latency",
            "situation": "API was slow under load",
            "task": "Reduce latency",
            "action": "Optimized query path",
            "result": "Latency dropped by 40%",
            "metric_text": "40%",
            "evidence_note": "Confirmed in review",
            "fact_status": "confirmed",
        },
        user_id="user-1",
    )

    assert snippet.title == "Reduced API latency"
    assert "python" not in snippet.skills
    assert "fastapi" in snippet.skills or "api" in snippet.snippet_text.lower()
    assert snippet.star_summary is not None
    assert snippet.star_summary.is_complete is True
    assert snippet.evidence_strength in {"strong", "medium"}


def test_strength_service_classifies_confident_metric_evidence_as_strong() -> None:
    service = EvidenceStrengthService()

    score = service.calculate_strength_score(
        {
            "title": "Scaled platform",
            "snippet_text": "Led kubernetes rollout and reduced latency by 35%",
            "metric_text": "35%",
            "evidence_note": "Confirmed by manager",
            "fact_status": "confirmed",
            "skills": ["kubernetes", "leadership", "python"],
            "star_summary": {
                "situation": "We had scaling issues",
                "task": "Increase capacity",
                "action": "Rolled out kubernetes",
                "result": "Latency fell",
            },
        }
    )

    assert score >= 0.7
    assert service.classify_strength(score) == "strong"


def test_selection_prefers_stronger_evidence_and_penalizes_overuse() -> None:
    service = EvidenceSelectionService()

    ranked = service.rank_evidence(
        query_text="python fastapi api",
        required_skills=["python", "fastapi"],
        source_types=["achievement"],
        evidence_items=[
            {
                "id": "e1",
                "title": "Strong python delivery",
                "snippet_text": "Built FastAPI service with measurable latency improvement",
                "source_type": "achievement",
                "skills": ["python", "fastapi"],
                "evidence_strength": "strong",
                "fact_status": "confirmed",
                "usage_count": 0,
                "used_in_documents_count": 0,
                "used_in_interviews_count": 0,
                "star_summary": {
                    "situation": "Situation",
                    "task": "Task",
                    "action": "Action",
                    "result": "Result",
                },
            },
            {
                "id": "e2",
                "title": "Weaker python note",
                "snippet_text": "Helped on python API work",
                "source_type": "achievement",
                "skills": ["python"],
                "evidence_strength": "weak",
                "fact_status": "partial",
                "usage_count": 8,
                "used_in_documents_count": 2,
                "used_in_interviews_count": 2,
                "star_summary": {},
            },
        ],
    )

    assert ranked
    assert ranked[0]["evidence_id"] == "e1"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_selection_prefers_confirmed_complete_star_evidence_over_unverified_alternative() -> None:
    service = EvidenceSelectionService()

    ranked = service.rank_evidence(
        query_text="python backend delivery",
        required_skills=["python", "backend"],
        evidence_items=[
            {
                "id": "confirmed",
                "title": "Confirmed delivery story",
                "snippet_text": "Built FastAPI service with PostgreSQL and launched it successfully",
                "source_type": "achievement",
                "skills": ["python", "fastapi"],
                "evidence_strength": "strong",
                "fact_status": "confirmed",
                "usage_count": 0,
                "used_in_documents_count": 0,
                "used_in_interviews_count": 0,
                "star_summary": {
                    "situation": "Need for a backend",
                    "task": "Ship the service",
                    "action": "Built FastAPI service",
                    "result": "Launched successfully",
                },
            },
            {
                "id": "unverified",
                "title": "Unverified delivery story",
                "snippet_text": "Built FastAPI service with PostgreSQL and launched it successfully",
                "source_type": "achievement",
                "skills": ["python", "fastapi"],
                "evidence_strength": "strong",
                "fact_status": "unverified",
                "usage_count": 0,
                "used_in_documents_count": 0,
                "used_in_interviews_count": 0,
                "star_summary": {
                    "situation": "Need for a backend",
                    "task": "Ship the service",
                    "action": "Built FastAPI service",
                    "result": "Launched successfully",
                },
            },
        ],
    )

    assert [item["evidence_id"] for item in ranked] == ["confirmed", "unverified"]
    assert ranked[0]["score"] > ranked[1]["score"]


def test_selection_penalizes_incomplete_star_structure() -> None:
    service = EvidenceSelectionService()

    ranked = service.rank_evidence(
        query_text="python api delivery",
        required_skills=["python", "api"],
        evidence_items=[
            {
                "id": "complete",
                "title": "Complete STAR story",
                "snippet_text": "Built a FastAPI service that reduced latency by 35%",
                "source_type": "achievement",
                "skills": ["python", "fastapi"],
                "evidence_strength": "medium",
                "fact_status": "confirmed",
                "usage_count": 0,
                "used_in_documents_count": 0,
                "used_in_interviews_count": 0,
                "star_summary": {
                    "situation": "Latency was high",
                    "task": "Improve performance",
                    "action": "Built FastAPI service",
                    "result": "Latency dropped by 35%",
                },
            },
            {
                "id": "incomplete",
                "title": "Incomplete STAR story",
                "snippet_text": "Built a FastAPI service that reduced latency by 35%",
                "source_type": "achievement",
                "skills": ["python", "fastapi"],
                "evidence_strength": "medium",
                "fact_status": "confirmed",
                "usage_count": 0,
                "used_in_documents_count": 0,
                "used_in_interviews_count": 0,
                "star_summary": {
                    "situation": "Latency was high",
                    "task": "Improve performance",
                    "action": "Built FastAPI service",
                    "result": "",
                },
            },
        ],
    )

    assert [item["evidence_id"] for item in ranked] == ["complete", "incomplete"]
    assert ranked[0]["score"] > ranked[1]["score"]
