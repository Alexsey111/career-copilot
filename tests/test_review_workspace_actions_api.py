from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import CandidateAchievement, CandidateProfile, DocumentVersion
from app.models.review_workflow import (
    ReviewActionRecord,
    ReviewOutcomeRecord,
    ReviewSessionRecord,
)


API_PREFIX = "/api/v1"


async def _create_document(db_session, *, user_id):
    document = DocumentVersion(
        id=uuid4(),
        user_id=user_id,
        vacancy_id=None,
        derived_from_id=None,
        analysis_id=None,
        source_recommendation_id=None,
        document_kind="resume",
        version_label="v1",
        review_status="draft",
        is_active=True,
        content_json={"sections": []},
        rendered_text="resume text",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def _create_achievement(db_session, *, user_id):
    profile = CandidateProfile(
        id=uuid4(),
        user_id=user_id,
        full_name="Test User",
        headline=None,
        location=None,
        summary=None,
        target_roles_json=[],
        work_format_preferences_json={},
        salary_expectation=None,
        salary_currency=None,
    )
    achievement = CandidateAchievement(
        id=uuid4(),
        profile_id=profile.id,
        experience_id=None,
        title="Built ETL pipeline",
        situation=None,
        task=None,
        action=None,
        result=None,
        metric_text=None,
        evidence_note=None,
        fact_status="needs_confirmation",
        order_index=0,
    )
    db_session.add_all([profile, achievement])
    await db_session.commit()
    await db_session.refresh(achievement)
    return achievement


@pytest.mark.asyncio
async def test_record_review_action_approve_claim_updates_fact_status(client, db_session, test_user):
    document = await _create_document(db_session, user_id=test_user.id)
    achievement = await _create_achievement(db_session, user_id=test_user.id)
    workspace_id = f"ws_{document.id}_{test_user.id}"

    response = await client.post(
        f"{API_PREFIX}/review/workspaces/{workspace_id}/actions",
        json={
            "action_type": "approve_claim",
            "target_type": "claim",
            "target_id": str(achievement.id),
            "payload": {
                "claim_text": "Built ETL pipeline",
                "evidence_note": " confirmed by reviewer ",
            },
            "reviewer_id": str(test_user.id),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workspace_id"] == workspace_id
    assert payload["action_type"] == "approve_claim"
    assert payload["status"] == "recorded"

    review_session = (
        await db_session.execute(
            select(ReviewSessionRecord).where(ReviewSessionRecord.document_id == document.id)
        )
    ).scalar_one()
    assert review_session.user_id == test_user.id
    assert review_session.status == "review_required"
    assert review_session.completed_at is None
    assert review_session.reviewer_id == test_user.id

    await db_session.refresh(achievement)
    assert achievement.fact_status == "confirmed"
    assert achievement.evidence_note == "confirmed by reviewer"

    action = (
        await db_session.execute(
            select(ReviewActionRecord).where(ReviewActionRecord.review_session_id == review_session.id)
        )
    ).scalar_one()
    assert action.action_type == "approve_claim"
    assert action.target_type == "claim"
    assert action.target_id == str(achievement.id)
    assert action.action_payload_json == {
        "claim_text": "Built ETL pipeline",
        "evidence_note": " confirmed by reviewer ",
    }


@pytest.mark.asyncio
async def test_record_review_action_reject_claim_updates_fact_status(client, db_session, test_user):
    document = await _create_document(db_session, user_id=test_user.id)
    achievement = await _create_achievement(db_session, user_id=test_user.id)
    workspace_id = f"ws_{document.id}_{test_user.id}"

    response = await client.post(
        f"{API_PREFIX}/review/workspaces/{workspace_id}/actions",
        json={
            "action_type": "reject_claim",
            "target_type": "claim",
            "target_id": str(achievement.id),
            "payload": {"evidence_note": "no proof"},
            "reviewer_id": str(test_user.id),
        },
    )

    assert response.status_code == 200, response.text
    await db_session.refresh(achievement)
    assert achievement.fact_status == "rejected"
    assert achievement.evidence_note == "no proof"


@pytest.mark.asyncio
async def test_record_review_action_completes_session_for_approve_document(client, db_session, test_user):
    document = await _create_document(db_session, user_id=test_user.id)
    workspace_id = f"ws_{document.id}_{test_user.id}"

    response = await client.post(
        f"{API_PREFIX}/review/workspaces/{workspace_id}/actions",
        json={
            "action_type": "approve_document",
            "target_type": "document",
            "target_id": str(document.id),
            "payload": {"reason": "ready to ship"},
            "reviewer_id": str(test_user.id),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["action_type"] == "approve_document"
    assert payload["status"] == "completed"

    review_session = (
        await db_session.execute(
            select(ReviewSessionRecord).where(ReviewSessionRecord.document_id == document.id)
        )
    ).scalar_one()
    assert review_session.completed_at is not None
    assert review_session.final_status == "approved"
    assert review_session.status == "approved"
    assert review_session.review_duration_ms is not None

    outcome = (
        await db_session.execute(
            select(ReviewOutcomeRecord).where(ReviewOutcomeRecord.review_session_id == review_session.id)
        )
    ).scalar_one()
    assert outcome.outcome_status == "approved"
    assert outcome.approved is True
    assert outcome.outcome_payload_json["workspace_id"] == workspace_id
    assert outcome.outcome_payload_json["action_type"] == "approve_document"


@pytest.mark.asyncio
async def test_record_review_action_rejects_invalid_claim_target_without_audit_trail(client, db_session, test_user):
    document = await _create_document(db_session, user_id=test_user.id)
    workspace_id = f"ws_{document.id}_{test_user.id}"

    response = await client.post(
        f"{API_PREFIX}/review/workspaces/{workspace_id}/actions",
        json={
            "action_type": "approve_claim",
            "target_type": "claim",
            "target_id": str(uuid4()),
            "reviewer_id": str(test_user.id),
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Claim target not found"

    action_count = (
        await db_session.execute(
            select(ReviewActionRecord)
        )
    ).scalars().all()
    session_count = (
        await db_session.execute(
            select(ReviewSessionRecord)
        )
    ).scalars().all()
    assert action_count == []
    assert session_count == []
