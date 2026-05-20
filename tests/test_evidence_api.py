from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.dependencies import get_current_active_user
from app.domain.evidence import EvidenceSourceType, build_evidence_fingerprint
from app.models import User
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.services.evidence_extraction_service import EvidenceExtractionService


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _seed_snippet(
    db_session,
    *,
    user_id,
    title: str,
    text: str,
    source_type: EvidenceSourceType | str = EvidenceSourceType.MANUAL,
) -> dict:
    extraction_service = EvidenceExtractionService()
    repository = EvidenceSnippetRepository()
    snippet = extraction_service.extract_from_text(
        title=title,
        text=text,
        user_id=str(user_id),
        source_type=source_type,
        fact_status="confirmed",
    )
    persisted = await repository.upsert_many(
        db_session,
        user_id=user_id,
        snippets=[extraction_service.snippet_to_dict(snippet)],
    )
    assert persisted, "Expected snippet to be persisted"
    return {
        "snippet": persisted[0],
        "payload": extraction_service.snippet_to_dict(snippet),
    }


async def _seed_custom_snippet(
    db_session,
    *,
    user_id,
    title: str,
    text: str,
    source_type: EvidenceSourceType | str = EvidenceSourceType.MANUAL,
    evidence_strength: str = "weak",
    fact_status: str = "unverified",
    usage_count: int = 0,
    used_in_documents_count: int = 0,
    used_in_interviews_count: int = 0,
    skills: list[str] | None = None,
    star_summary: dict[str, str] | None = None,
) -> dict:
    repository = EvidenceSnippetRepository()
    payload = {
        "fingerprint": build_evidence_fingerprint(
            user_id=str(user_id),
            title=title,
            snippet_text=text,
            source_type=str(source_type),
            skills=skills or [],
            fact_status=fact_status,
        ),
        "title": title,
        "snippet_text": text,
        "source_type": str(source_type),
        "skills": skills or [],
        "evidence_strength": evidence_strength,
        "fact_status": fact_status,
        "usage_count": usage_count,
        "used_in_documents_count": used_in_documents_count,
        "used_in_interviews_count": used_in_interviews_count,
        "star_summary": star_summary or {},
    }
    persisted = await repository.upsert_many(
        db_session,
        user_id=user_id,
        snippets=[payload],
    )
    assert persisted, "Expected snippet to be persisted"
    return {
        "snippet": persisted[0],
        "payload": payload,
    }


async def test_evidence_snippets_api_returns_user_snippets(client, db_session, test_user) -> None:
    other_user = User(
        email=f"other-{uuid4().hex}@local.test",
        password_hash="hash",
        auth_provider="test",
    )
    db_session.add(other_user)
    await db_session.flush()

    current_seed = await _seed_snippet(
        db_session,
        user_id=test_user.id,
        title="Python backend delivery",
        text="Built a Python FastAPI backend with PostgreSQL and metrics.",
    )
    await _seed_snippet(
        db_session,
        user_id=other_user.id,
        title="Leadership story",
        text="Led a cross-functional team through a release.",
    )

    response = await client.get(f"{API_PREFIX}/evidence/snippets")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["id"] == str(current_seed["snippet"].id)
    assert payload[0]["title"] == "Python backend delivery"
    assert "skills" in payload[0]
    assert isinstance(payload[0]["skills"], list)
    assert "star_summary" in payload[0]
    assert isinstance(payload[0]["star_summary"], dict)

    def override_other_user():
        return SimpleNamespace(id=other_user.id, is_active=True, is_verified=True)

    from app.main import app

    app.dependency_overrides[get_current_active_user] = override_other_user
    try:
        other_response = await client.get(f"{API_PREFIX}/evidence/snippets")
        assert other_response.status_code == 200, other_response.text

        other_payload = other_response.json()
        assert isinstance(other_payload, list)
        assert len(other_payload) == 1
        assert other_payload[0]["title"] == "Leadership story"
    finally:
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
            id=test_user.id,
            is_active=True,
            is_verified=True,
        )


async def test_get_evidence_snippet_api_returns_item(client, db_session, test_user) -> None:
    seed = await _seed_snippet(
        db_session,
        user_id=test_user.id,
        title="Confirmed FastAPI project",
        text="Delivered a FastAPI service with PostgreSQL and Docker.",
    )

    response = await client.get(f"{API_PREFIX}/evidence/snippets/{seed['snippet'].id}")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["id"] == str(seed["snippet"].id)
    assert payload["title"] == "Confirmed FastAPI project"
    assert payload["fact_status"] == "confirmed"
    assert "skills" in payload
    assert isinstance(payload["skills"], list)
    assert "star_summary" in payload
    assert isinstance(payload["star_summary"], dict)


async def test_get_evidence_snippet_api_returns_404_for_unknown_id(client) -> None:
    response = await client.get(f"{API_PREFIX}/evidence/snippets/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Evidence snippet not found"


async def test_evidence_usages_api_returns_user_usages(client, db_session, test_user) -> None:
    seed = await _seed_snippet(
        db_session,
        user_id=test_user.id,
        title="Interview story",
        text="Explained a release incident and how the team recovered.",
    )

    repository = EvidenceSnippetRepository()
    await repository.record_usage(
        db_session,
        user_id=test_user.id,
        evidence_snippet_id=seed["snippet"].id,
        usage_type="interview",
        target_type="question",
        target_id="question-1",
        note="Used in interview prep",
    )

    response = await client.get(f"{API_PREFIX}/evidence/usages")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["evidence_snippet_id"] == str(seed["snippet"].id)
    assert payload[0]["usage_type"] == "interview"


async def test_get_evidence_insights_api_returns_counts_and_recommendations(
    client,
    db_session,
    test_user,
) -> None:
    other_user = User(
        email=f"other-insights-{uuid4().hex}@local.test",
        password_hash="hash",
        auth_provider="test",
    )
    db_session.add(other_user)
    await db_session.flush()

    await _seed_custom_snippet(
        db_session,
        user_id=test_user.id,
        title="Weak unverified story",
        text="Helped with onboarding tasks",
        evidence_strength="weak",
        fact_status="unverified",
        usage_count=0,
        skills=["python"],
        star_summary={},
    )
    await _seed_custom_snippet(
        db_session,
        user_id=test_user.id,
        title="Overused partial story",
        text="Built API workflow and reduced manual handoffs by 35%",
        evidence_strength="medium",
        fact_status="confirmed",
        usage_count=4,
        used_in_documents_count=2,
        used_in_interviews_count=1,
        skills=["python", "fastapi"],
        star_summary={
            "situation": "We needed an internal workflow",
            "task": "Automate the process",
            "action": "Built API workflow",
            "result": "2 teams used it",
        },
    )
    await _seed_custom_snippet(
        db_session,
        user_id=test_user.id,
        title="Confirmed strong metric story",
        text="Reduced latency by 35% and launched FastAPI service",
        evidence_strength="strong",
        fact_status="confirmed",
        usage_count=1,
        used_in_documents_count=1,
        used_in_interviews_count=0,
        skills=["python", "fastapi"],
        star_summary={
            "situation": "Latency was high",
            "task": "Improve performance",
            "action": "Launched FastAPI service",
            "result": "Latency dropped by 35%",
        },
    )
    await _seed_custom_snippet(
        db_session,
        user_id=test_user.id,
        title="Unused partial story",
        text="Implemented internal dashboard",
        evidence_strength="weak",
        fact_status="partial",
        usage_count=0,
        skills=["python"],
        star_summary={
            "situation": "Team lacked a dashboard",
            "task": "Create internal reporting",
            "action": "",
            "result": "",
        },
    )

    await _seed_custom_snippet(
        db_session,
        user_id=other_user.id,
        title="Other user snippet",
        text="Built a separate backend",
        evidence_strength="weak",
        fact_status="unverified",
        usage_count=0,
        skills=["python"],
        star_summary={},
    )

    response = await client.get(f"{API_PREFIX}/evidence/insights")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["weak_evidence_count"] == 2
    assert payload["missing_metrics_count"] == 2
    assert payload["missing_star_fields_count"] == 2
    assert payload["unused_evidence_count"] == 2
    assert payload["overused_evidence_count"] == 1
    assert payload["unverified_evidence_count"] == 2

    recommendations = payload["recommendations"]
    assert isinstance(recommendations, list)
    assert len(recommendations) == 11

    recommendation_types = {item["type"] for item in recommendations}
    assert {
        "weak_evidence",
        "missing_metric",
        "incomplete_star",
        "unused_evidence",
        "overused_evidence",
        "unverified_evidence",
    }.issubset(recommendation_types)

    for recommendation in recommendations:
        assert recommendation["evidence_id"] is not None
        assert recommendation["title"]

    def override_other_user():
        return SimpleNamespace(id=other_user.id, is_active=True, is_verified=True)

    from app.main import app

    app.dependency_overrides[get_current_active_user] = override_other_user
    try:
        other_response = await client.get(f"{API_PREFIX}/evidence/insights")
        assert other_response.status_code == 200, other_response.text

        other_payload = other_response.json()
        assert other_payload["weak_evidence_count"] == 1
        assert other_payload["missing_metrics_count"] == 1
        assert other_payload["missing_star_fields_count"] == 1
        assert other_payload["unused_evidence_count"] == 1
        assert other_payload["overused_evidence_count"] == 0
        assert other_payload["unverified_evidence_count"] == 1
    finally:
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
            id=test_user.id,
            is_active=True,
            is_verified=True,
        )
