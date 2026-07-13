from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, CandidateTargetTrack, User
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _create_profile(db_session: AsyncSession, test_user: User) -> CandidateProfile:
    profile_repo = CandidateProfileRepository()
    profile = await profile_repo.create_empty(db_session, user_id=test_user.id)
    profile.target_roles_json = ["Backend Engineer", "Platform Engineer"]
    await db_session.commit()
    return profile


async def _seed_vacancies_with_gaps(
    db_session: AsyncSession, test_user: User
) -> None:
    """Три вакансии с recurring gap "Kubernetes" (critical)."""
    vacancy_repo = VacancyRepository()
    analysis_repo = VacancyAnalysisRepository()

    for title in ("Senior Backend Engineer", "Platform Engineer", "Staff Backend Engineer"):
        vacancy = await vacancy_repo.create(
            db_session,
            user_id=test_user.id,
            source="manual",
            source_url=None,
            external_id=None,
            title=title,
            company="Acme",
            location="Remote",
            description_raw="Must have: Kubernetes, Python.",
            normalized_json={"requirements": ["Kubernetes", "Python"]},
        )
        await analysis_repo.replace_for_vacancy(
            db_session,
            vacancy_id=vacancy.id,
            must_have_json=[
                {"text": "Kubernetes"},
                {"text": "Python"},
            ],
            nice_to_have_json=[{"text": "Redis"}],
            keywords_json=["Kubernetes", "Python", "Redis"],
            gaps_json=[
                {"text": "Kubernetes", "severity": "critical"},
            ],
            strengths_json=[{"text": "Python"}],
            match_score=70,
            analysis_version="deterministic_v1",
        )
    await db_session.commit()


async def _create_foreign_track(
    db_session: AsyncSession, test_user: User
) -> CandidateTargetTrack:
    """Track, принадлежащий ДРУГОМУ user (для ownership-тестов)."""
    foreign_user = User(
        email=f"foreign-{uuid4().hex}@local.test",
        password_hash="x",
        auth_provider="test",
    )
    db_session.add(foreign_user)
    await db_session.flush()
    foreign_profile = CandidateProfile(user_id=foreign_user.id)
    db_session.add(foreign_profile)
    await db_session.flush()
    track = CandidateTargetTrack(
        profile_id=foreign_profile.id,
        name="Foreign track",
        target_roles_json=["Data Scientist"],
    )
    db_session.add(track)
    await db_session.commit()
    return track


async def test_post_then_get_returns_work_format_and_order_index(
    client, db_session, test_user
) -> None:
    await _create_profile(db_session, test_user)

    create = await client.post(
        f"{API_PREFIX}/profile/target-tracks",
        json={
            "name": "Platform path",
            "target_roles": ["Platform Engineer"],
            "work_format": {"remote": True},
            "order_index": 2,
            "priority": 5,
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["work_format"] == {"remote": True}
    assert body["order_index"] == 2
    assert body["priority"] == 5
    track_id = body["id"]

    listing = await client.get(f"{API_PREFIX}/profile/target-tracks")
    assert listing.status_code == 200, listing.text
    tracks = listing.json()
    assert any(t["id"] == track_id and t["work_format"] == {"remote": True} for t in tracks)


async def test_create_target_track_rejects_unknown_field(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    resp = await client.post(
        f"{API_PREFIX}/profile/target-tracks",
        json={"name": "x", "unexpected_field": 1},
    )
    assert resp.status_code == 422


async def test_patch_target_track_partial_update(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    create = await client.post(
        f"{API_PREFIX}/profile/target-tracks",
        json={"name": "Track", "target_roles": ["Backend Engineer"], "priority": 1},
    )
    assert create.status_code == 200, create.text
    track_id = create.json()["id"]

    patch = await client.patch(
        f"{API_PREFIX}/profile/target-tracks/{track_id}",
        json={"priority": 9},
    )
    assert patch.status_code == 200, patch.text
    patched = patch.json()
    assert patched["priority"] == 9
    # Остальные поля нетронуты.
    assert patched["name"] == "Track"
    assert patched["target_roles"] == ["Backend Engineer"]


async def test_patch_target_track_empty_body_is_noop(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    create = await client.post(
        f"{API_PREFIX}/profile/target-tracks",
        json={"name": "Track", "priority": 3},
    )
    track_id = create.json()["id"]

    patch = await client.patch(
        f"{API_PREFIX}/profile/target-tracks/{track_id}",
        json={},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["priority"] == 3


async def test_patch_target_track_404_when_not_owned(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    foreign = await _create_foreign_track(db_session, test_user)

    patch = await client.patch(
        f"{API_PREFIX}/profile/target-tracks/{foreign.id}",
        json={"priority": 7},
    )
    assert patch.status_code == 404
    assert patch.json()["detail"] == "target track not found"


async def test_patch_target_track_404_when_missing(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    patch = await client.patch(
        f"{API_PREFIX}/profile/target-tracks/{uuid4()}",
        json={"priority": 7},
    )
    assert patch.status_code == 404


async def test_delete_target_track_404_when_not_owned(client, db_session, test_user) -> None:
    """Этап 9.D: фикс бага — раньше чужой track удалялся (нет ownership)."""
    await _create_profile(db_session, test_user)
    foreign = await _create_foreign_track(db_session, test_user)

    delete = await client.delete(f"{API_PREFIX}/profile/target-tracks/{foreign.id}")
    assert delete.status_code == 404
    assert delete.json()["detail"] == "target track not found"


async def test_delete_target_track_own_succeeds(client, db_session, test_user) -> None:
    from sqlalchemy import select

    await _create_profile(db_session, test_user)
    create = await client.post(
        f"{API_PREFIX}/profile/target-tracks",
        json={"name": "Mine"},
    )
    track_id = create.json()["id"]

    delete = await client.delete(f"{API_PREFIX}/profile/target-tracks/{track_id}")
    assert delete.status_code == 200, delete.text
    assert delete.json() == {"status": "deleted"}

    # Прямой select по id — шаримая сессия + relationship-кэш могут
    # показывать удалённый track в GET list, поэтому проверяем в БД.
    result = await db_session.execute(
        select(CandidateTargetTrack).where(
            CandidateTargetTrack.id == UUID(track_id)
        )
    )
    assert result.scalar_one_or_none() is None


async def test_get_strategy_returns_explainable_report(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    await _seed_vacancies_with_gaps(db_session, test_user)

    create = await client.post(
        f"{API_PREFIX}/profile/target-tracks",
        json={"name": "Platform", "target_roles": ["Platform Engineer"]},
    )
    assert create.status_code == 200, create.text
    track_id = create.json()["id"]

    resp = await client.get(f"{API_PREFIX}/profile/target-tracks/{track_id}/strategy")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["track_id"] == track_id
    assert body["gap_summary"]
    k8s = next(g for g in body["gap_summary"] if g["keyword"] == "Kubernetes")
    assert k8s["is_relevant_to_track"] is True
    assert k8s["severity"] == "critical"

    steps = body["learning_plan"]["steps"]
    assert steps
    assert any(s["gap_keyword"] == "Kubernetes" for s in steps)
    # non-goal: никаких ссылок на курсы в action/rationale.
    for s in steps:
        text = f"{s['action']} {s['rationale']}".casefold()
        assert "http" not in text and "курс" not in text

    assert body["search_tactics"]
    assert body["provenance"]["requires_human_review"] is True
    assert "gap_trend" in body["provenance"]["sources"]


async def test_get_strategy_404_when_not_owned(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    foreign = await _create_foreign_track(db_session, test_user)

    resp = await client.get(f"{API_PREFIX}/profile/target-tracks/{foreign.id}/strategy")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "target track not found"


async def test_get_strategy_404_when_missing(client, db_session, test_user) -> None:
    await _create_profile(db_session, test_user)
    resp = await client.get(f"{API_PREFIX}/profile/target-tracks/{uuid4()}/strategy")
    assert resp.status_code == 404