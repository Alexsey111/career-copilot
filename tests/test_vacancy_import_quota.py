# tests\test_vacancy_import_quota.py

"""Demo-режим: лимит импорта вакансий (3) в скользящем часовом окне.

``vacancy_import`` — единственное действие квоты с секундным (а не дневным)
окном (``demo_vacancy_import_window_seconds``, по умолчанию 3600). После 3
импортов в течение часа 4-й → 402; когда старые импорты выпадают из окна,
лимит снова доступен (скользящее окно моделирует «3 в час, потом ждать час»).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.billing import (
    PLAN_FREE,
    QUOTA_VACANCY_IMPORT,
)
from app.models import Vacancy
from app.services.quota_service import QuotaService

API_PREFIX = "/api/v1"


def _restore_limits() -> None:
    get_settings.cache_clear()


async def _add_vacancy(
    session: AsyncSession,
    *,
    user_id,
    created_at: datetime | None = None,
) -> None:
    session.add(
        Vacancy(
            user_id=user_id,
            title="Demo vacancy",
            description_raw="desc",
            source="manual",
            created_at=created_at or datetime.now(timezone.utc),
        )
    )
    await session.flush()


# --- Metering: count_usage (секундное окно) ---------------------------------


@pytest.mark.asyncio
async def test_count_vacancy_import_uses_hour_window(db_session, test_user):
    # Один импорт сейчас + один 2 часа назад. Часовое окно (3600с) → только
    # свежий попадает в счёт.
    now = datetime.now(timezone.utc)
    await _add_vacancy(db_session, user_id=test_user.id, created_at=now)
    await _add_vacancy(
        db_session, user_id=test_user.id, created_at=now - timedelta(hours=2)
    )

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert used == 1


@pytest.mark.asyncio
async def test_count_vacancy_import_window_configurable(db_session, test_user, monkeypatch):
    # Окно задаётся через DEMO_VACANCY_IMPORT_WINDOW_SECONDS. С окном в 1 час
    # 2-часовой импорт исключается; с окном в 3 часа — включается.
    now = datetime.now(timezone.utc)
    await _add_vacancy(db_session, user_id=test_user.id, created_at=now)
    await _add_vacancy(
        db_session, user_id=test_user.id, created_at=now - timedelta(hours=2)
    )

    monkeypatch.setenv("DEMO_VACANCY_IMPORT_WINDOW_SECONDS", "10800")  # 3 часа
    get_settings.cache_clear()
    try:
        service = QuotaService()
        used = await service.count_usage(
            db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
        )
        assert used == 2
    finally:
        _restore_limits()


# --- check_quota: 3 разрешено, 4-й блок -------------------------------------


@pytest.mark.asyncio
async def test_check_quota_vacancy_import_allows_three(db_session, test_user):
    # Лимит 3 = максимум 3 импорта. Проверка идёт ДО действия: used=2 → 3-й
    # импорт ещё разрешён (2 < 3). used=3 (после 3 импортов) блокирует 4-й.
    service = QuotaService()
    for _ in range(2):
        await _add_vacancy(db_session, user_id=test_user.id)
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert decision.allowed is True
    assert decision.plan == PLAN_FREE
    assert decision.limit == 3
    assert decision.used == 2


@pytest.mark.asyncio
async def test_check_quota_vacancy_import_blocks_fourth(db_session, test_user):
    # Лимит 3: после 3 импортов 4-й запрещён (used=3, 3 < 3 → False).
    service = QuotaService()
    for _ in range(3):
        await _add_vacancy(db_session, user_id=test_user.id)
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    # used == 3 == limit → allowed False (3 < 3 ложно)
    assert decision.allowed is False
    assert decision.used == 3
    assert decision.limit == 3
    assert decision.reason is not None
    assert "vacancy_import" in decision.reason


@pytest.mark.asyncio
async def test_check_quota_vacancy_import_refills_after_window(db_session, test_user):
    # 3 импорта 2 часа назад выпадают из часового окна → лимит снова доступен.
    now = datetime.now(timezone.utc)
    for _ in range(3):
        await _add_vacancy(
            db_session, user_id=test_user.id, created_at=now - timedelta(hours=2)
        )
    service = QuotaService()
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert decision.allowed is True
    assert decision.used == 0  # в окне ничего нет


# --- get_usage: window_seconds для vacancy_import ---------------------------


@pytest.mark.asyncio
async def test_get_usage_reports_window_seconds_for_vacancy_import(db_session, test_user):
    service = QuotaService()
    usage = await service.get_usage(db_session, user_id=test_user.id)
    entry = usage[QUOTA_VACANCY_IMPORT]
    assert entry["limit"] == 3
    assert entry["window_seconds"] == 3600
    assert "window_days" not in entry  # секундное окно не сообщает дни


# --- Enforcement 402 (endpoint) --------------------------------------------


@pytest.mark.asyncio
async def test_vacancy_import_endpoint_402_after_three(client, test_user):
    # 3 импорта проходят, 4-й → 402 с action=vacancy_import.
    payload = {"source": "manual", "description_raw": "demo vacancy text"}
    for i in range(3):
        resp = await client.post(f"{API_PREFIX}/vacancies/import", json=payload)
        assert resp.status_code == 200, resp.text

    resp = await client.post(f"{API_PREFIX}/vacancies/import", json=payload)
    assert resp.status_code == 402, resp.text
    detail = resp.json()["detail"]
    assert detail["action"] == "vacancy_import"
    assert detail["plan"] == "free"
    assert detail["used"] == 3
    assert detail["limit"] == 3
    assert "reason" in detail


@pytest.mark.asyncio
async def test_vacancy_import_quota_configurable_via_env(client, test_user, monkeypatch):
    # Лимит можно опустить до 0 через env → первый же импорт 402.
    monkeypatch.setenv("BILLING_FREE_TIER_VACANCY_IMPORTS_LIMIT", "0")
    get_settings.cache_clear()
    try:
        resp = await client.post(
            f"{API_PREFIX}/vacancies/import",
            json={"source": "manual", "description_raw": "demo"},
        )
        assert resp.status_code == 402, resp.text
        assert resp.json()["detail"]["action"] == "vacancy_import"
    finally:
        _restore_limits()