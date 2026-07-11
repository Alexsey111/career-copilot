# tests/test_consent_enforcement.py

"""Enforcement согласий: required-consent блокирует обработку (ФЗ-152 ст.6/9)."""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.models import UserConsent

pytestmark = pytest.mark.asyncio


async def test_ai_consent_missing_blocks_endpoint(client, db_session, test_user):
    await db_session.execute(
        delete(UserConsent).where(
            UserConsent.user_id == test_user.id,
            UserConsent.consent_type == "ai_generation",
        )
    )
    await db_session.flush()

    resp = await client.post("/api/v1/profile/repository-achievements/generate")
    assert resp.status_code == 403
    assert "consent" in resp.json()["detail"].lower()


async def test_ai_consent_present_allows_endpoint(client, test_user):
    # Согласие выдано по умолчанию в фикстуре test_user → эндпоинт проходит
    # consent-проверку и возвращает 400 (нет профиля), но не 403.
    resp = await client.post("/api/v1/profile/repository-achievements/generate")
    assert resp.status_code != 403


async def test_data_processing_consent_missing_blocks_intake(
    client, db_session, test_user
):
    await db_session.execute(
        delete(UserConsent).where(
            UserConsent.user_id == test_user.id,
            UserConsent.consent_type == "data_processing",
        )
    )
    await db_session.flush()

    resp = await client.post(
        "/api/v1/profile/intake/manual",
        json={},
    )
    assert resp.status_code == 403