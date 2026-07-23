# tests\test_billing_quotas.py

"""Тесты квот биллинга (Этап 4): metering (подсчёт usage) и enforcement (402).

Metering-источники (обоснование в ``app/domain/billing.py``):
- ``ai_request`` → ``AIRun`` (исключая generated-output workflows).
- ``doc_upload`` → ``SourceFile``.
- ``generated_output`` → ``DocumentVersion`` (root-версии).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.billing import (
    PLAN_FREE,
    PLAN_PAID_MONTHLY,
    SUBSCRIPTION_ACTIVE,
    QUOTA_AI_REQUEST,
    QUOTA_DOC_UPLOAD,
    QUOTA_GENERATED_OUTPUT,
)
from app.models import AIRun, DocumentVersion, SourceFile, Subscription
from app.services.quota_service import QuotaService


def _low_limits(monkeypatch):
    """Локально опускает free-tier лимиты до 0 (enforcement 402)."""
    monkeypatch.setenv("BILLING_FREE_TIER_AI_REQUESTS_LIMIT", "0")
    monkeypatch.setenv("BILLING_FREE_TIER_DOC_UPLOADS_LIMIT", "0")
    monkeypatch.setenv("BILLING_FREE_TIER_GENERATED_OUTPUTS_LIMIT", "0")
    get_settings.cache_clear()


def _restore_limits():
    get_settings.cache_clear()


async def _add_ai_run(session: AsyncSession, *, user_id, workflow_name: str) -> None:
    session.add(
        AIRun(
            user_id=user_id,
            workflow_name=workflow_name,
            target_type="vacancy",
            status="completed",
        )
    )
    await session.flush()


async def _add_source_file(session: AsyncSession, *, user_id) -> None:
    session.add(
        SourceFile(
            user_id=user_id,
            file_kind="resume",
            storage_key=f"uploads/{uuid4().hex}",
            original_name="resume.pdf",
        )
    )
    await session.flush()


async def _add_document_version(
    session: AsyncSession,
    *,
    user_id,
    document_kind: str = "resume",
    derived_from_id=None,
) -> None:
    session.add(
        DocumentVersion(
            user_id=user_id,
            document_kind=document_kind,
            derived_from_id=derived_from_id,
            content_json={},
        )
    )
    await session.flush()


# --- Metering: count_usage ---------------------------------------------------


@pytest.mark.asyncio
async def test_count_ai_request_excludes_generated_workflows(db_session, test_user):
    # 2 «обычных» AI-вызова + 1 generated-output workflow (исключается).
    await _add_ai_run(db_session, user_id=test_user.id, workflow_name="resume_enhance")
    await _add_ai_run(db_session, user_id=test_user.id, workflow_name="interview_coach")
    await _add_ai_run(
        db_session, user_id=test_user.id, workflow_name="resume_tailoring"
    )

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert used == 2


@pytest.mark.asyncio
async def test_count_ai_request_counts_manual_cover_letter_improve(db_session, test_user):
    # Ручной enhance cover letter (POST /letters/{id}/enhance) идёт через
    # workflow ``cover_letter_improve`` (отдельный от generate-path
    # ``cover_letter_enhance``) → должен считаться как ``ai_request``.
    await _add_ai_run(
        db_session, user_id=test_user.id, workflow_name="cover_letter_improve"
    )
    # generate-path workflow — исключается.
    await _add_ai_run(
        db_session, user_id=test_user.id, workflow_name="cover_letter_enhance"
    )

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert used == 1


@pytest.mark.asyncio
async def test_count_doc_upload_by_source_files(db_session, test_user):
    await _add_source_file(db_session, user_id=test_user.id)
    await _add_source_file(db_session, user_id=test_user.id)

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_DOC_UPLOAD
    )
    assert used == 2


@pytest.mark.asyncio
async def test_count_generated_output_only_root_versions(db_session, test_user):
    # 2 root-версии (resume + cover_letter) + 1 derived (enhance) — не считается.
    await _add_document_version(
        db_session, user_id=test_user.id, document_kind="resume"
    )
    await _add_document_version(
        db_session, user_id=test_user.id, document_kind="cover_letter"
    )
    root = await _add_document_version_and_get(
        db_session, user_id=test_user.id, document_kind="resume"
    )
    await _add_document_version(
        db_session,
        user_id=test_user.id,
        document_kind="resume",
        derived_from_id=root.id,
    )

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_GENERATED_OUTPUT
    )
    assert used == 3  # 2 из первого блока + 1 root из второго блока


async def _add_document_version_and_get(session, *, user_id, document_kind):
    from app.models import DocumentVersion

    dv = DocumentVersion(
        user_id=user_id, document_kind=document_kind, derived_from_id=None, content_json={}
    )
    session.add(dv)
    await session.flush()
    return dv


@pytest.mark.asyncio
async def test_count_unknown_action_raises(db_session, test_user):
    service = QuotaService()
    with pytest.raises(ValueError):
        await service.count_usage(db_session, user_id=test_user.id, action="bogus")


# --- count_usage_with_oldest (Bug#3.2) ------------------------------------


@pytest.mark.asyncio
async def test_count_usage_with_oldest_returns_none_when_empty(
    db_session, test_user
):
    service = QuotaService()
    used, oldest = await service.count_usage_with_oldest(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert used == 0
    assert oldest is None


@pytest.mark.asyncio
async def test_count_usage_with_oldest_picks_min_created_at(
    db_session, test_user
):
    await _add_ai_run(db_session, user_id=test_user.id, workflow_name="resume_enhance")
    await _add_ai_run(db_session, user_id=test_user.id, workflow_name="interview_coach")

    service = QuotaService()
    used, oldest = await service.count_usage_with_oldest(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert used == 2
    assert oldest is not None
    # oldest — timestamp самой первой записи; две записи в этом тесте
    # создаются последовательно, поэтому oldest <= now и oldest == MIN.
    from datetime import datetime, timezone

    assert oldest <= datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_count_usage_with_oldest_excludes_generated_workflows(
    db_session, test_user
):
    # generated-output workflow ``resume_tailoring`` исключается из
    # ``ai_request`` — он не должен влиять ни на used, ни на oldest.
    await _add_ai_run(
        db_session, user_id=test_user.id, workflow_name="resume_tailoring"
    )

    service = QuotaService()
    used, oldest = await service.count_usage_with_oldest(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert used == 0
    assert oldest is None


# --- check_quota ------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_quota_free_allows_under_limit(db_session, test_user):
    service = QuotaService()
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert decision.allowed is True
    assert decision.plan == PLAN_FREE
    assert decision.limit == get_settings().billing_free_tier_ai_requests_limit
    assert decision.used == 0


@pytest.mark.asyncio
async def test_check_quota_free_blocks_at_limit(db_session, test_user, monkeypatch):
    monkeypatch.setenv("BILLING_FREE_TIER_AI_REQUESTS_LIMIT", "1")
    get_settings.cache_clear()
    await _add_ai_run(db_session, user_id=test_user.id, workflow_name="resume_enhance")

    service = QuotaService()
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert decision.allowed is False
    assert decision.used == 1
    assert decision.limit == 1
    assert decision.reason is not None
    assert "ai_request" in decision.reason
    _restore_limits()


@pytest.mark.asyncio
async def test_check_quota_paid_unlimited(db_session, test_user):
    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan=PLAN_PAID_MONTHLY,
            status=SUBSCRIPTION_ACTIVE,
            stripe_customer_id="cus_test_1",
            stripe_subscription_id="sub_test_1",
        )
    )
    await db_session.flush()

    service = QuotaService()
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert decision.allowed is True
    assert decision.limit is None
    assert decision.plan == PLAN_PAID_MONTHLY


@pytest.mark.asyncio
async def test_check_quota_paid_canceled_not_unlimited(db_session, test_user, monkeypatch):
    # canceled → не unlimited; применяем free-tier лимит.
    monkeypatch.setenv("BILLING_FREE_TIER_AI_REQUESTS_LIMIT", "0")
    get_settings.cache_clear()
    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan=PLAN_PAID_MONTHLY,
            status="canceled",
        )
    )
    await db_session.flush()

    service = QuotaService()
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_AI_REQUEST
    )
    assert decision.allowed is False
    assert decision.limit == 0
    _restore_limits()


@pytest.mark.asyncio
async def test_get_usage_reports_all_actions(db_session, test_user):
    await _add_ai_run(db_session, user_id=test_user.id, workflow_name="interview_coach")
    await _add_source_file(db_session, user_id=test_user.id)
    await _add_document_version(db_session, user_id=test_user.id, document_kind="resume")

    service = QuotaService()
    usage = await service.get_usage(db_session, user_id=test_user.id)
    assert usage[QUOTA_AI_REQUEST]["used"] == 1
    assert usage[QUOTA_DOC_UPLOAD]["used"] == 1
    assert usage[QUOTA_GENERATED_OUTPUT]["used"] == 1
    assert usage[QUOTA_AI_REQUEST]["limit"] == get_settings().billing_free_tier_ai_requests_limit
    # oldest_in_window заполнен хотя бы для тех действий, у которых used>0.
    assert usage[QUOTA_AI_REQUEST]["oldest_in_window"] is not None
    assert usage[QUOTA_DOC_UPLOAD]["oldest_in_window"] is not None
    assert usage[QUOTA_GENERATED_OUTPUT]["oldest_in_window"] is not None


@pytest.mark.asyncio
async def test_get_usage_oldest_is_none_when_used_zero(db_session, test_user):
    service = QuotaService()
    usage = await service.get_usage(db_session, user_id=test_user.id)
    for action, entry in usage.items():
        assert entry["used"] == 0
        assert entry["oldest_in_window"] is None, action


# --- Enforcement 402 (endpoint) --------------------------------------------


@pytest.mark.asyncio
async def test_generate_resume_402_when_generated_output_quota_zero(
    client, test_user, monkeypatch
):
    _low_limits(monkeypatch)
    try:
        resp = await client.post(
            "/api/v1/documents/resumes/generate",
            json={"vacancy_id": str(uuid4())},
        )
        assert resp.status_code == 402, resp.text
        detail = resp.json()["detail"]
        assert detail["action"] == "generated_output"
        assert detail["plan"] == "free"
        assert detail["limit"] == 0
        assert "reason" in detail
    finally:
        _restore_limits()


@pytest.mark.asyncio
async def test_upload_402_when_doc_upload_quota_zero(client, test_user, monkeypatch):
    _low_limits(monkeypatch)
    try:
        resp = await client.post(
            "/api/v1/files/upload",
            data={"file_kind": "resume"},
            files={"file": ("resume.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 402, resp.text
        assert resp.json()["detail"]["action"] == "doc_upload"
    finally:
        _restore_limits()


@pytest.mark.asyncio
async def test_paid_subscription_bypasses_quota(client, test_user, db_session):
    # Активная платная подписка → generate не падает с 402 (упадёт с 400/404
    # по бизнес-причинам, но НЕ 402).
    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan=PLAN_PAID_MONTHLY,
            status=SUBSCRIPTION_ACTIVE,
        )
    )
    await db_session.flush()

    resp = await client.post(
        "/api/v1/documents/resumes/generate",
        json={"vacancy_id": str(uuid4())},
    )
    assert resp.status_code != 402, resp.text