"""
Тесты для endpoint GET /documents/{document_id}/diff/{other_document_id}
"""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _prepare_profile(client) -> None:
    """Загружает фейковый PDF и создаёт профиль."""
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

    structured_response = await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    assert structured_response.status_code == 200, structured_response.text

    achievements_response = await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )
    assert achievements_response.status_code == 200, achievements_response.text


async def _create_analyzed_vacancy(client) -> str:
    """Создаёт вакансию и запускает анализ."""
    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "description_raw": (
                "Требования:\n"
                "- Python\n"
                "- FastAPI\n"
                "- PostgreSQL\n"
            ),
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy_id = vacancy_response.json()["vacancy_id"]

    analysis_response = await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze",
    )
    assert analysis_response.status_code == 200, analysis_response.text

    return vacancy_id


async def _create_resume(client, vacancy_id: str) -> str:
    """Генерирует резюме и возвращает document_id."""
    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert generate_response.status_code == 200
    return generate_response.json()["document_id"]


@pytest.mark.asyncio
async def test_document_diff_success(client, db_session, test_user):
    """Тест что diff между двумя версиями возвращает unified diff."""
    from uuid import uuid4
    from app.repositories.document_version_repository import DocumentVersionRepository

    repo = DocumentVersionRepository()

    # Создаём два документа напрямую через репозиторий
    from app.models.entities import DocumentVersion

    # vacancy_id=None чтобы не создавать vacancy
    vacancy_id = None

    document_a = DocumentVersion(
        id=uuid4(),
        user_id=test_user.id,
        vacancy_id=vacancy_id,
        derived_from_id=None,
        analysis_id=None,
        document_kind="resume",
        version_label="resume_draft_v1",
        review_status="draft",
        is_active=True,
        content_json={"document_kind": "resume"},
        rendered_text="Line 1\nLine 2\nLine 3",
    )
    db_session.add(document_a)

    document_b = DocumentVersion(
        id=uuid4(),
        user_id=test_user.id,
        vacancy_id=vacancy_id,
        derived_from_id=document_a.id,
        analysis_id=None,
        document_kind="resume",
        version_label="resume_enhanced_v1",
        review_status="draft",
        is_active=False,
        content_json={"document_kind": "resume"},
        rendered_text="Line 1\nLine 2 MODIFIED\nLine 3\nNew Line 4",
    )
    db_session.add(document_b)
    await db_session.flush()

    # Запрашиваем diff
    diff_response = await client.get(
        f"{API_PREFIX}/documents/{document_a.id}/diff/{document_b.id}"
    )

    assert diff_response.status_code == 200
    diff_data = diff_response.json()

    assert diff_data["document_id"] == str(document_a.id)
    assert diff_data["other_document_id"] == str(document_b.id)
    assert diff_data["document_kind"] == "resume"
    assert "---" in diff_data["diff"]
    assert "+++" in diff_data["diff"]
    assert "MODIFIED" in diff_data["diff"] or "- Line 2" in diff_data["diff"]


@pytest.mark.asyncio
async def test_document_diff_rejects_different_document_kind(client):
    """Тест что diff между разными типами документов возвращает 400."""
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    # Создаём резюме
    resume_id = await _create_resume(client, vacancy_id)

    # Создаём сопроводительное письмо
    cover_letter_response = await client.post(
        f"{API_PREFIX}/documents/letters/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert cover_letter_response.status_code == 200
    cover_letter_id = cover_letter_response.json()["document_id"]

    # Запрашиваем diff между резюме и письмом
    diff_response = await client.get(
        f"{API_PREFIX}/documents/{resume_id}/diff/{cover_letter_id}"
    )

    assert diff_response.status_code == 400
    assert "same document_kind" in diff_response.json()["detail"]


@pytest.mark.asyncio
async def test_document_diff_requires_same_user(client, test_user):
    """Тест что нельзя делать diff чужих документов."""
    from uuid import uuid4

    # Создаём document_id для несуществующего документа
    fake_document_id = str(uuid4())
    fake_other_document_id = str(uuid4())

    # Запрашиваем diff несуществующих документов
    diff_response = await client.get(
        f"{API_PREFIX}/documents/{fake_document_id}/diff/{fake_other_document_id}"
    )

    assert diff_response.status_code == 404
