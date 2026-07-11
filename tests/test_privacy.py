# tests/test_privacy.py

"""Права субъекта ПДн и политика конфиденциальности (ФЗ-152)."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.models import (
    AuthEvent,
    CandidateProfile,
    DataTransferEvent,
    DocumentVersion,
    EvidenceSnippet,
    User,
    UserConsent,
)

pytestmark = pytest.mark.asyncio

PRIVACY_PREFIX = "/api/v1/privacy"


async def test_privacy_policy_endpoint(client):
    resp = await client.get(f"{PRIVACY_PREFIX}/policy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"]
    assert "legal_basis" in body
    assert "categories_of_data" in body
    assert "subject_rights" in body
    assert any("export" in r for r in body["subject_rights"])


async def test_export_my_data_returns_user_pii(client, db_session, test_user):
    profile = CandidateProfile(
        user_id=test_user.id,
        full_name="Иван Тестов",
        location="Москва",
        summary="Python-разработчик",
    )
    db_session.add(profile)
    db_session.add(
        EvidenceSnippet(
            user_id=test_user.id,
            fingerprint="fp-export-1",
            title="Достижение",
            snippet_text="Сократил расходы на 30%",
        )
    )
    db_session.add(
        DocumentVersion(
            user_id=test_user.id,
            document_kind="resume",
            rendered_text="Моё резюме",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/me/data/export")
    assert resp.status_code == 200
    body = resp.json()

    assert body["user"]["email"] == test_user.email
    assert body["profile"] is not None
    assert body["profile"]["full_name"] == "Иван Тестов"
    assert body["profile"]["location"] == "Москва"
    assert any(e["snippet_text"] == "Сократил расходы на 30%" for e in body["evidence_snippets"])
    assert any(d["rendered_text"] == "Моё резюме" for d in body["document_versions"])
    # Согласия попадают в выгрузку.
    assert len(body["consents"]) >= 3


async def test_export_data_is_decrypted(client, db_session, test_user):
    """Шифрованные поля должны возвращаться в открытом виде (ст.14 доступ)."""
    db_session.add(
        EvidenceSnippet(
            user_id=test_user.id,
            fingerprint="fp-decrypt-1",
            title="",
            snippet_text="Секретный текст 123",
        )
    )
    await db_session.commit()

    # На уровне БД (raw SQL, минуя ORM-декоратор) — токен, не plaintext.
    raw = (
        await db_session.execute(
            text(
                "SELECT snippet_text FROM evidence_snippets "
                "WHERE fingerprint = :fp"
            ),
            {"fp": "fp-decrypt-1"},
        )
    ).scalar_one()
    assert "Секретный текст 123" not in raw

    resp = await client.get("/api/v1/me/data/export")
    assert resp.status_code == 200
    snippets = resp.json()["evidence_snippets"]
    assert any(s["snippet_text"] == "Секретный текст 123" for s in snippets)


async def test_delete_my_data_erases_and_anonymizes_audit(
    client, db_session, test_user
):
    user_id = test_user.id

    # Существующие audit-события пользователя.
    db_session.add(
        AuthEvent(
            user_id=user_id,
            event_type="login_success",
            email=test_user.email,
            meta_json={},
        )
    )
    db_session.add(
        DataTransferEvent(
            user_id=user_id,
            recipient="gigachat",
            purpose="test",
            data_categories=["personal_data"],
            legal_basis="consent",
        )
    )
    await db_session.commit()

    resp = await client.delete("/api/v1/me/data")
    assert resp.status_code == 204

    # Пользователь и его ПДн удалены.
    assert (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(UserConsent).where(UserConsent.user_id == user_id)
        )
    ).scalars().all() == []

    # Журналы учёта обезличены: нет ссылок на user_id, но событие об удалении
    # зафиксировано (ФЗ-152 ст.19 — журналы учёта сохраняются).
    remaining_auth = (
        await db_session.execute(select(AuthEvent))
    ).scalars().all()
    assert all(a.user_id is None for a in remaining_auth)
    assert any(a.event_type == "data_erasure_requested" for a in remaining_auth)

    remaining_transfers = (
        await db_session.execute(select(DataTransferEvent))
    ).scalars().all()
    assert all(t.user_id is None for t in remaining_transfers)