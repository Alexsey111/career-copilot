# tests\test_vacancy_import_quota.py

"""Demo-режим: лимит на запуск анализа вакансии (3) в скользящем часовом окне.

После редизайна квоты (см. ``app/domain/billing.py`` ``QUOTA_VACANCY_IMPORT``)
«vacancy_import» считается по запускам **анализа** (таблица
``vacancy_analyses``), а НЕ по самому импорту вакансии — то есть вставка
текста / URL / файла бесплатны, можно править сколько угодно, а слот
списывается когда AI реально потратился на анализ.

Окно — секундное (``demo_vacancy_import_window_seconds``, по умолчанию
3600). После 3 запусков анализа в течение часа 4-й → 402.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.billing import (
    PLAN_FREE,
    QUOTA_VACANCY_IMPORT,
)
from app.models import Vacancy, VacancyAnalysis
from app.services.quota_service import QuotaService

API_PREFIX = "/api/v1"


def _restore_limits() -> None:
    get_settings.cache_clear()


async def _add_vacancy_with_analysis(
    session: AsyncSession,
    *,
    user_id,
    created_at: datetime | None = None,
) -> None:
    """Создать вакансию + связанный анализ (имитация успешного analyze).

    Квота ``vacancy_import`` теперь меряется по ``vacancy_analyses.created_at``,
    поэтому для проверки metering нужны оба объекта.
    """
    when = created_at or datetime.now(timezone.utc)
    vacancy = Vacancy(
        user_id=user_id,
        title="Demo vacancy",
        description_raw="desc",
        source="manual",
        created_at=when,
    )
    session.add(vacancy)
    await session.flush()
    session.add(
        VacancyAnalysis(
            vacancy_id=vacancy.id,
            must_have_json=[],
            nice_to_have_json=[],
            keywords_json=[],
            gaps_json=[],
            strengths_json=[],
            analysis_version="deterministic_v1",
            created_at=when,
        )
    )
    await session.flush()


# --- Metering: count_usage (секундное окно) ---------------------------------


@pytest.mark.asyncio
async def test_count_vacancy_import_uses_hour_window(db_session, test_user):
    # Один анализ сейчас + один 2 часа назад. Часовое окно (3600с) → только
    # свежий попадает в счёт.
    now = datetime.now(timezone.utc)
    await _add_vacancy_with_analysis(
        db_session, user_id=test_user.id, created_at=now
    )
    await _add_vacancy_with_analysis(
        db_session, user_id=test_user.id, created_at=now - timedelta(hours=2)
    )

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert used == 1


@pytest.mark.asyncio
async def test_count_vacancy_import_ignores_vacancies_without_analysis(
    db_session, test_user
):
    # «Голый» импорт вакансии (без анализа) НЕ должен списывать слот.
    db_session.add(
        Vacancy(
            user_id=test_user.id,
            title="Demo vacancy",
            description_raw="desc",
            source="manual",
        )
    )
    await db_session.flush()

    service = QuotaService()
    used = await service.count_usage(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert used == 0


@pytest.mark.asyncio
async def test_count_vacancy_import_window_configurable(
    db_session, test_user, monkeypatch
):
    # Окно задаётся через DEMO_VACANCY_IMPORT_WINDOW_SECONDS. С окном в 1 час
    # 2-часовой анализ исключается; с окном в 3 часа — включается.
    now = datetime.now(timezone.utc)
    await _add_vacancy_with_analysis(
        db_session, user_id=test_user.id, created_at=now
    )
    await _add_vacancy_with_analysis(
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
    # Лимит 3 = максимум 3 анализа. used=2 → 3-й ещё разрешён.
    service = QuotaService()
    for _ in range(2):
        await _add_vacancy_with_analysis(db_session, user_id=test_user.id)
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert decision.allowed is True
    assert decision.plan == PLAN_FREE
    assert decision.limit == 3
    assert decision.used == 2


@pytest.mark.asyncio
async def test_check_quota_vacancy_import_blocks_fourth(db_session, test_user):
    # Лимит 3: после 3 анализов 4-й запрещён (used=3, 3 < 3 → False).
    service = QuotaService()
    for _ in range(3):
        await _add_vacancy_with_analysis(db_session, user_id=test_user.id)
    decision = await service.check_quota(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert decision.allowed is False
    assert decision.used == 3
    assert decision.limit == 3
    assert decision.reason is not None
    assert "vacancy_import" in decision.reason


@pytest.mark.asyncio
async def test_check_quota_vacancy_import_refills_after_window(
    db_session, test_user
):
    # 3 анализа 2 часа назад выпадают из часового окна → лимит снова доступен.
    now = datetime.now(timezone.utc)
    for _ in range(3):
        await _add_vacancy_with_analysis(
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
async def test_get_usage_reports_window_seconds_for_vacancy_import(
    db_session, test_user
):
    service = QuotaService()
    usage = await service.get_usage(db_session, user_id=test_user.id)
    entry = usage[QUOTA_VACANCY_IMPORT]
    assert entry["limit"] == 3
    assert entry["window_seconds"] == 3600
    assert "window_days" not in entry  # секундное окно не сообщает дни


# --- Enforcement 402 (endpoint) --------------------------------------------
#
# Квота теперь висит на /analyze, а не на /import. Импорт вакансии — бесплатный.


@pytest.mark.asyncio
async def test_vacancy_import_endpoint_does_not_consume_quota(client, test_user):
    # 5 импортов подряд проходят без 402 — квота больше не на /import.
    payload = {"source": "manual", "description_raw": "demo vacancy text"}
    for i in range(5):
        resp = await client.post(f"{API_PREFIX}/vacancies/import", json=payload)
        assert resp.status_code == 200, (i, resp.text)


@pytest.mark.asyncio
async def test_vacancy_analyze_endpoint_402_after_three(
    client, test_user, db_session
):
    # 3 импорта + 3 анализа проходят, 4-й analyze → 402.
    payload = {"source": "manual", "description_raw": "demo vacancy text"}
    vacancy_ids: list[str] = []
    for _ in range(4):
        resp = await client.post(f"{API_PREFIX}/vacancies/import", json=payload)
        assert resp.status_code == 200, resp.text
        vacancy_ids.append(resp.json()["vacancy_id"])

    for vid in vacancy_ids[:3]:
        resp = await client.post(f"{API_PREFIX}/vacancies/{vid}/analyze")
        assert resp.status_code == 200, (vid, resp.text)

    resp = await client.post(f"{API_PREFIX}/vacancies/{vacancy_ids[3]}/analyze")
    assert resp.status_code == 402, resp.text
    detail = resp.json()["detail"]
    assert detail["action"] == "vacancy_import"
    assert detail["plan"] == "free"
    assert detail["used"] == 3
    assert detail["limit"] == 3
    assert "reason" in detail


@pytest.mark.asyncio
async def test_vacancy_analyze_quota_configurable_via_env(
    client, test_user, monkeypatch
):
    # Лимит можно опустить до 0 через env → первый же analyze 402.
    payload = {"source": "manual", "description_raw": "demo"}
    resp = await client.post(f"{API_PREFIX}/vacancies/import", json=payload)
    assert resp.status_code == 200, resp.text
    vid = resp.json()["vacancy_id"]

    monkeypatch.setenv("BILLING_FREE_TIER_VACANCY_IMPORTS_LIMIT", "0")
    get_settings.cache_clear()
    try:
        resp = await client.post(f"{API_PREFIX}/vacancies/{vid}/analyze")
        assert resp.status_code == 402, resp.text
        assert resp.json()["detail"]["action"] == "vacancy_import"
    finally:
        _restore_limits()


# --- oldest_in_window для countdown ----------------------------------------


@pytest.mark.asyncio
async def test_vacancy_import_oldest_in_window_picks_min_analysis(
    db_session, test_user
):
    """Bug#3.2: oldest берётся из vacancy_analyses (а не vacancies)."""
    now = datetime.now(timezone.utc)
    await _add_vacancy_with_analysis(
        db_session, user_id=test_user.id, created_at=now - timedelta(minutes=5)
    )
    await _add_vacancy_with_analysis(
        db_session, user_id=test_user.id, created_at=now
    )

    service = QuotaService()
    used, oldest = await service.count_usage_with_oldest(
        db_session, user_id=test_user.id, action=QUOTA_VACANCY_IMPORT
    )
    assert used == 2
    assert oldest is not None
    # oldest — самая старая запись (5 мин назад), не самая новая.
    assert oldest <= now - timedelta(minutes=4)
