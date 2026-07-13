from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.career_strategy_service import CareerStrategyService


def _track(track_id, target_roles=None):
    return SimpleNamespace(
        id=track_id,
        profile_id=uuid4(),
        target_roles_json=list(target_roles or []),
        location_preferences_json=[],
        work_format_json={},
        salary_expectation=None,
        salary_currency=None,
        priority=0,
        is_active=True,
        notes=None,
        order_index=0,
    )


class _GapTrendService:
    def __init__(self, gaps, vacancy_samples=None):
        self._gaps = gaps
        self._vacancy_samples = vacancy_samples

    async def build_gap_trends(self, session, *, user_id, limit=20):  # noqa: D401
        return {
            "top_recurring_gaps": self._gaps,
            "vacancy_samples": self._vacancy_samples if self._vacancy_samples is not None else [],
        }


class _FailingGapTrendService:
    async def build_gap_trends(self, session, *, user_id, limit=20):  # noqa: D401
        raise HTTPException(status_code=400, detail="gap trends unavailable")


class _ProfileRepo:
    def __init__(self, profile=None):
        self._profile = profile

    async def get_with_related_by_user_id(self, session, user_id):  # noqa: D401
        return self._profile


def _profile(track, target_roles_json=None):
    return SimpleNamespace(
        target_tracks=[track],
        target_roles_json=target_roles_json or [],
    )


_GAPS = [
    {
        "keyword": "Kubernetes",
        "count": 3,
        "severity": "critical",
        "example_vacancy_titles": ["Platform Engineer"],
    },
    {
        "keyword": "1с бухгалтерия",
        "count": 2,
        "severity": "critical",
        "example_vacancy_titles": ["Бухгалтер"],
    },
]


@pytest.mark.asyncio
async def test_build_strategy_classifies_relevant_vs_other_gaps() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=["Backend Engineer", "Platform Engineer"])
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS, vacancy_samples=[{"vacancy_title": "X"}]),
        profile_repo=_ProfileRepo(_profile(track)),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)

    summary = report["gap_summary"]
    assert len(summary) == 2
    k8s = next(g for g in summary if g["keyword"] == "Kubernetes")
    book = next(g for g in summary if g["keyword"] == "1с бухгалтерия")
    assert k8s["is_relevant_to_track"] is True
    assert book["is_relevant_to_track"] is False
    assert book["relevance_reason"] == "not in target role scope"


@pytest.mark.asyncio
async def test_build_strategy_learning_plan_only_for_relevant_gaps() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=["Platform Engineer"])
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS, vacancy_samples=[{"vacancy_title": "X"}]),
        profile_repo=_ProfileRepo(_profile(track)),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    steps = report["learning_plan"]["steps"]
    # Только Kubernetes relevant → шаги только про него.
    keywords = {s["gap_keyword"] for s in steps}
    assert "Kubernetes" in keywords
    assert "1с бухгалтерия" not in keywords
    assert report["provenance"]["requires_human_review"] is True
    assert report["provenance"]["confidence"] == "medium"
    assert "gap_trend" in report["provenance"]["sources"]


@pytest.mark.asyncio
async def test_build_strategy_confidence_is_low_without_vacancy_samples() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=["Backend Engineer"])
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS, vacancy_samples=[]),
        profile_repo=_ProfileRepo(_profile(track)),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    assert report["provenance"]["confidence"] == "low"
    assert any("human" in note for note in report["provenance"]["notes"])


@pytest.mark.asyncio
async def test_build_strategy_degrades_when_gap_trends_unavailable() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=["Backend Engineer"])
    service = CareerStrategyService(
        gap_trend_service=_FailingGapTrendService(),
        profile_repo=_ProfileRepo(_profile(track)),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    assert report["gap_summary"] == []
    assert report["learning_plan"]["steps"] == []
    assert report["provenance"]["confidence"] == "low"
    assert report["search_tactics"]  # generic tactics всё равно есть


@pytest.mark.asyncio
async def test_build_strategy_falls_back_to_profile_target_roles() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=[])  # пусто на треке
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS, vacancy_samples=[{"vacancy_title": "X"}]),
        profile_repo=_ProfileRepo(_profile(track, target_roles_json=["Backend Engineer"])),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    k8s = next(g for g in report["gap_summary"] if g["keyword"] == "Kubernetes")
    assert k8s["is_relevant_to_track"] is True


@pytest.mark.asyncio
async def test_build_strategy_404_when_track_not_owned() -> None:
    track_id = uuid4()
    # В профиле другой track.
    profile = SimpleNamespace(
        target_tracks=[_track(uuid4(), target_roles=["Backend Engineer"])],
        target_roles_json=[],
    )
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS),
        profile_repo=_ProfileRepo(profile),
    )

    with pytest.raises(HTTPException) as exc:
        await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "target track not found"


@pytest.mark.asyncio
async def test_build_strategy_404_when_profile_missing() -> None:
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS),
        profile_repo=_ProfileRepo(None),
    )

    with pytest.raises(HTTPException) as exc:
        await service.build_strategy(None, user_id=uuid4(), track_id=uuid4())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_build_strategy_adds_generic_tactics_note_when_no_target_roles() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=[])
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS, vacancy_samples=[{"vacancy_title": "X"}]),
        profile_repo=_ProfileRepo(_profile(track, target_roles_json=[])),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    assert any("generic" in note for note in report["provenance"]["notes"])


@pytest.mark.asyncio
async def test_build_strategy_track_id_serialized_as_string() -> None:
    track_id = uuid4()
    track = _track(track_id, target_roles=["Backend Engineer"])
    service = CareerStrategyService(
        gap_trend_service=_GapTrendService(_GAPS, vacancy_samples=[{"vacancy_title": "X"}]),
        profile_repo=_ProfileRepo(_profile(track)),
    )

    report = await service.build_strategy(None, user_id=uuid4(), track_id=track_id)
    assert report["track_id"] == str(track_id)