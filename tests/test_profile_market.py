# tests/test_profile_market.py

"""Этап 7 — переключатель юрисдикции/рынка (RU/EU/US): автодетект из location,
проводка через intake, PATCH /profile/market, присутствие в pipeline state."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.profile_structuring_service import ProfileStructuringService


API_PREFIX = "/api/v1"


# --- Unit: автодетект рынка из location ---

def test_infer_market_ru_from_russia_location() -> None:
    service = ProfileStructuringService()
    assert service._infer_market_from_location("Москва, Россия") == "RU"


def test_infer_market_ru_from_city_prefix() -> None:
    service = ProfileStructuringService()
    assert service._infer_market_from_location("г. Санкт-Петербург") == "RU"


def test_infer_market_eu_from_berlin() -> None:
    service = ProfileStructuringService()
    assert service._infer_market_from_location("Berlin, Germany") == "EU"


def test_infer_market_us_from_san_francisco() -> None:
    service = ProfileStructuringService()
    assert service._infer_market_from_location("San Francisco, CA, USA") == "US"


def test_infer_market_unknown_returns_none() -> None:
    service = ProfileStructuringService()
    assert service._infer_market_from_location("Remote") is None
    assert service._infer_market_from_location("") is None


def test_apply_profile_fields_infers_market_when_unset() -> None:
    service = ProfileStructuringService()
    profile = SimpleNamespace(
        full_name=None,
        headline=None,
        location=None,
        summary=None,
        target_roles_json=None,
        technologies_json=None,
        market=None,
    )
    draft = SimpleNamespace(
        full_name=None,
        headline=None,
        location="Москва, Россия",
        summary=None,
        target_roles=[],
        technologies=[],
    )

    service._apply_profile_fields(profile, draft)

    assert profile.market == "RU"


def test_apply_profile_fields_does_not_override_explicit_market() -> None:
    service = ProfileStructuringService()
    profile = SimpleNamespace(
        full_name=None,
        headline=None,
        location=None,
        summary=None,
        target_roles_json=None,
        technologies_json=None,
        market="EU",
    )
    draft = SimpleNamespace(
        full_name=None,
        headline=None,
        location="Москва, Россия",
        summary=None,
        target_roles=[],
        technologies=[],
    )

    service._apply_profile_fields(profile, draft)

    # Явно заданный user-override не перетирается автодетектом.
    assert profile.market == "EU"


def test_apply_profile_fields_skips_inference_without_location() -> None:
    service = ProfileStructuringService()
    profile = SimpleNamespace(
        full_name=None,
        headline=None,
        location=None,
        summary=None,
        target_roles_json=None,
        technologies_json=None,
        market=None,
    )
    draft = SimpleNamespace(
        full_name=None,
        headline=None,
        location=None,
        summary=None,
        target_roles=[],
        technologies=[],
    )

    service._apply_profile_fields(profile, draft)

    assert profile.market is None


# --- API: PATCH /profile/market ---

@pytest.mark.asyncio
async def test_patch_market_updates_profile(client) -> None:
    # Сначала создаём профиль через manual intake.
    intake = await client.post(
        f"{API_PREFIX}/profile/intake/manual",
        json={
            "personal": {
                "name": "Market Tester",
                "location": "Remote",
                "target_role": "Backend Developer",
            },
            "skills": {"technologies": [], "ai_tools": [], "automation_tools": []},
            "experience": [],
            "projects": [],
            "education": [],
        },
    )
    assert intake.status_code == 200, intake.text
    assert intake.json()["market"] is None

    response = await client.patch(f"{API_PREFIX}/profile/market", json={"market": "EU"})

    assert response.status_code == 200, response.text
    assert response.json() == {"market": "EU"}

    # Проводка в pipeline state.
    state = await client.get(f"{API_PREFIX}/profile/resume-state")
    assert state.status_code == 200, state.text
    assert state.json()["structured_profile"]["market"] == "EU"


@pytest.mark.asyncio
async def test_patch_market_rejects_invalid_value(client) -> None:
    response = await client.patch(f"{API_PREFIX}/profile/market", json={"market": "XX"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_market_404_when_no_profile(client) -> None:
    # У test_user нет профиля, пока intake не запускался.
    response = await client.patch(f"{API_PREFIX}/profile/market", json={"market": "US"})

    assert response.status_code == 404


# --- API: intake проводит market в ответ ---

@pytest.mark.asyncio
async def test_manual_intake_with_market_in_response(client) -> None:
    response = await client.post(
        f"{API_PREFIX}/profile/intake/manual",
        json={
            "personal": {
                "name": "Market Tester",
                "location": "Berlin",
                "target_role": "Data Engineer",
                "market": "US",
            },
            "skills": {"technologies": [], "ai_tools": [], "automation_tools": []},
            "experience": [],
            "projects": [],
            "education": [],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["market"] == "US"