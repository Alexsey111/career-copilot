"""Тесты ``/profile/resumes`` (листинг + reuse).

Сценарий:
- пользователь загрузил несколько версий резюме (PDF/DOCX), прошёл парсинг
- загрузил ещё одну → старые стали superseded, новая active
- может переключаться между ними через ``/reuse`` (без reparse) или
  ``/reuse?reparse=true`` (новый FileExtraction)
- изоляция по user_id (чужой 404)
- ``include_superseded=false`` фильтрует

Использует существующие ``SourceFileRepository``/``FileExtractionRepository``
и сервис ``ProfileImportService.import_resume``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import FileExtraction, SourceFile
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository


API_PREFIX = "/api/v1"
pytestmark = pytest.mark.asyncio


async def _upload_resume(client, *, filename: str, content: bytes) -> dict:
    response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _import_resume(client, *, source_file_id: str) -> dict:
    response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_list_resumes_returns_empty_for_new_user(client) -> None:
    response = await client.get(f"{API_PREFIX}/profile/resumes")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"] == []
    assert payload["total"] == 0
    assert payload["active_source_file_id"] is None


async def test_list_resumes_returns_one_item_with_preview_after_import(
    client,
) -> None:
    uploaded = await _upload_resume(
        client,
        filename="resume-v1.pdf",
        content=b"%PDF-1.4 fake but importable",
    )
    import_result = await _import_resume(
        client, source_file_id=uploaded["id"],
    )

    response = await client.get(f"{API_PREFIX}/profile/resumes")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1

    item = payload["items"][0]
    assert item["id"] == uploaded["id"]
    assert item["lifecycle_status"] == "active"
    assert item["is_active"] is True
    # Новый файл уже active → reuse не имеет смысла
    assert item["is_reusable"] is False
    assert item["latest_extraction_id"] == import_result["extraction_id"]
    assert item["text_preview"] is not None
    assert item["detected_format"] in {"pdf", "txt", "docx", "unknown"}
    assert payload["active_source_file_id"] == uploaded["id"]


async def test_list_resumes_includes_superseded_with_timeline(
    client,
) -> None:
    v1 = await _upload_resume(
        client, filename="resume-v1.pdf", content=b"%PDF-v1",
    )
    await _import_resume(client, source_file_id=v1["id"])
    v2 = await _upload_resume(
        client, filename="resume-v2.pdf", content=b"%PDF-v2",
    )
    await _import_resume(client, source_file_id=v2["id"])
    v3 = await _upload_resume(
        client, filename="resume-v3.pdf", content=b"%PDF-v3",
    )
    await _import_resume(client, source_file_id=v3["id"])

    # По умолчанию include_superseded=true — все три
    response = await client.get(f"{API_PREFIX}/profile/resumes")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 3
    statuses = {item["lifecycle_status"] for item in payload["items"]}
    assert statuses == {"active", "superseded"}
    active = [it for it in payload["items"] if it["is_active"]][0]
    assert active["id"] == v3["id"]
    assert payload["active_source_file_id"] == v3["id"]

    # include_superseded=false — только активный
    response_active = await client.get(
        f"{API_PREFIX}/profile/resumes?include_superseded=false",
    )
    assert response_active.status_code == 200, response_active.text
    payload_active = response_active.json()
    assert payload_active["total"] == 1
    assert payload_active["items"][0]["id"] == v3["id"]


async def test_reuse_activates_superseded_without_reparse(client) -> None:
    v1 = await _upload_resume(
        client, filename="resume-v1.pdf", content=b"%PDF-v1",
    )
    await _import_resume(client, source_file_id=v1["id"])
    v2 = await _upload_resume(
        client, filename="resume-v2.pdf", content=b"%PDF-v2",
    )
    await _import_resume(client, source_file_id=v2["id"])

    # v1 теперь superseded
    response = await client.get(f"{API_PREFIX}/profile/resumes")
    items = {it["id"]: it for it in response.json()["items"]}
    assert items[v1["id"]]["lifecycle_status"] == "superseded"
    assert items[v1["id"]]["is_reusable"] is True

    # Reuse v1 (без reparse)
    reuse = await client.post(
        f"{API_PREFIX}/profile/resumes/{v1['id']}/reuse",
    )
    assert reuse.status_code == 200, reuse.text
    payload = reuse.json()
    assert payload["source_file_id"] == v1["id"]
    assert payload["reused"] is True
    assert payload["reparse_performed"] is False
    assert payload["extraction_id"] is not None
    assert payload["text_preview"] is not None
    # Возвращаем последний extraction от v1 (тот же, что был при import)
    expected_extraction = items[v1["id"]]["latest_extraction_id"]
    assert payload["extraction_id"] == expected_extraction

    # Проверяем, что v1 теперь active, v2 — superseded
    response_after = await client.get(f"{API_PREFIX}/profile/resumes")
    after_items = {it["id"]: it for it in response_after.json()["items"]}
    assert after_items[v1["id"]]["is_active"] is True
    assert after_items[v2["id"]]["is_active"] is False
    assert after_items[v2["id"]]["superseded_by_id"] == v1["id"]
    assert response_after.json()["active_source_file_id"] == v1["id"]


async def test_reuse_with_reparse_creates_new_extraction(
    client,
    db_session,
) -> None:
    uploaded = await _upload_resume(
        client, filename="resume.pdf", content=b"%PDF-reparse",
    )
    first = await _import_resume(client, source_file_id=uploaded["id"])

    # Reuse с reparse=true — создаст новый FileExtraction
    reuse = await client.post(
        f"{API_PREFIX}/profile/resumes/{uploaded['id']}/reuse?reparse=true",
    )
    assert reuse.status_code == 200, reuse.text
    payload = reuse.json()
    assert payload["reparse_performed"] is True
    assert payload["reused"] is False
    assert payload["extraction_id"] != first["extraction_id"]

    # В БД теперь 2 extraction для этого SourceFile
    extraction_repo = FileExtractionRepository()
    latest = await extraction_repo.get_latest_for_source_file(
        db_session, source_file_id=uploaded["id"],
    )
    assert latest is not None
    assert str(latest.id) == payload["extraction_id"]


async def test_reuse_404_for_foreign_source_file(
    client,
    db_session,
    test_user,
) -> None:
    """Чужой SourceFile → 404 (без утечки существования)."""
    other_repo = SourceFileRepository()
    # Создаём SourceFile от имени другого пользователя напрямую через репо.
    other_source = await other_repo.create(
        db_session,
        user_id=test_user.id,  # владелец — текущий user
        file_kind="resume",
        storage_key="other-user/resume/x.pdf",
        original_name="x.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        content_sha256="a" * 64,
    )
    # Удаляем из владельца — зальём чужой user_id через прямой update.
    # Проще: создать ещё одного user'а.
    from app.models import User
    from app.security.passwords import hash_password

    other_user = User(
        email="other@test.local",
        password_hash=hash_password("x"),
        auth_provider="local",
    )
    db_session.add(other_user)
    await db_session.flush()
    await db_session.refresh(other_user)

    foreign_source = await other_repo.create(
        db_session,
        user_id=other_user.id,  # чужой
        file_kind="resume",
        storage_key=f"{other_user.id}/resume/y.pdf",
        original_name="y.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        content_sha256="b" * 64,
    )

    # cleanup test_user source — нам не нужен
    await db_session.delete(other_source)
    await db_session.commit()

    response = await client.post(
        f"{API_PREFIX}/profile/resumes/{foreign_source.id}/reuse",
    )
    assert response.status_code == 404


async def test_reuse_400_for_non_resume_source_file(
    client,
    db_session,
    test_user,
) -> None:
    repo = SourceFileRepository()
    vacancy_source = await repo.create(
        db_session,
        user_id=test_user.id,
        file_kind="vacancy",
        storage_key=f"{test_user.id}/vacancy/z.pdf",
        original_name="z.pdf",
        mime_type="application/pdf",
        size_bytes=10,
    )
    response = await client.post(
        f"{API_PREFIX}/profile/resumes/{vacancy_source.id}/reuse",
    )
    assert response.status_code == 400


async def test_reuse_on_unparsed_resume_returns_needs_import(
    client,
) -> None:
    """Файл загружен, но никогда не парсился → status='needs_import'."""
    uploaded = await _upload_resume(
        client, filename="never-parsed.pdf", content=b"%PDF-never",
    )
    # НЕ вызываем /profile/import-resume — файл без extraction

    response = await client.post(
        f"{API_PREFIX}/profile/resumes/{uploaded['id']}/reuse",
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "needs_import"
    assert payload["extraction_id"] is None
    assert payload["reused"] is False
    # activate сработал, active_source_file_id теперь этот
    assert payload["source_file_id"] == uploaded["id"]


async def test_list_resumes_isolates_by_user(
    client,
    db_session,
) -> None:
    """Чужой SourceFile не виден в листинге."""
    from app.models import User
    from app.security.passwords import hash_password

    other_user = User(
        email="isolation@test.local",
        password_hash=hash_password("x"),
        auth_provider="local",
    )
    db_session.add(other_user)
    await db_session.flush()
    await db_session.refresh(other_user)

    other_repo = SourceFileRepository()
    await other_repo.create(
        db_session,
        user_id=other_user.id,
        file_kind="resume",
        storage_key=f"{other_user.id}/resume/other.pdf",
        original_name="other.pdf",
        mime_type="application/pdf",
        size_bytes=10,
    )

    # Загрузим что-то от текущего
    await _upload_resume(client, filename="mine.pdf", content=b"%PDF-mine")

    response = await client.get(f"{API_PREFIX}/profile/resumes")
    assert response.status_code == 200, response.text
    payload = response.json()
    # Только наш, чужой не виден
    assert payload["total"] == 1
    assert all("other" not in it["original_name"] for it in payload["items"])
