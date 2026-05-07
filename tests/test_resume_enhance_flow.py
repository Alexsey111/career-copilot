"""
Тест сценарий: generate → enhance → проверить derived_from_id

Ожидаемое поведение:
1. generate → document A (derived_from_id = NULL)
2. enhance → document B (derived_from_id = A)
"""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID

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
                "\n"
                "Будет плюсом:\n"
                "- Redis\n"
                "- Docker\n"
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


@pytest.mark.asyncio
async def test_resume_generate_then_enhance_creates_version_with_derived_from_id(client, db_session):
    """Тест что enhance создаёт новую версию с derived_from_id указывающим на исходный документ."""
    from sqlalchemy import select
    from app.repositories.document_version_repository import DocumentVersionRepository
    from app.models.entities import DocumentVersion
    from app.ai.clients.base import BaseLLMClient

    # Mock LLM client для enhance
    class MockEnhanceClient(BaseLLMClient):
        @property
        def provider_name(self) -> str:
            return "mock"

        async def aclose(self):
            pass

        async def generate(self, prompt: str, **kwargs):
            return {
                "content": "Enhanced: Built robust microservices with FastAPI and PostgreSQL.",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                "model": kwargs.get("model", "mock"),
                "finish_reason": "stop",
            }

        async def generate_structured(self, prompt: str, output_schema: dict, **kwargs):
            return {
                "content": {"enhanced_text": "Enhanced: Built robust microservices with FastAPI and PostgreSQL."},
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                "model": kwargs.get("model"),
            }

    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    repo = DocumentVersionRepository()

    # --- ШАГ 1: generate резюме ---
    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert generate_response.status_code == 200, generate_response.text
    document_a_id = generate_response.json()["document_id"]

    # Получаем document A
    doc_a_response = await client.get(f"{API_PREFIX}/documents/{document_a_id}")
    assert doc_a_response.status_code == 200
    document_a = doc_a_response.json()
    original_rendered = document_a["rendered_text"]

    # --- ШАГ 2: enhance резюме с mock client ---
    # Патчим AIOrchestrator чтобы использовать mock client
    from app.ai.orchestrator import AIOrchestrator

    mock_client = MockEnhanceClient()

    with patch.object(AIOrchestrator, '__init__', lambda self, client: None), \
         patch.object(AIOrchestrator, 'execute', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = {
            "result": {"enhanced_text": "Enhanced: Built robust microservices with FastAPI and PostgreSQL."}
        }

        enhance_response = await client.post(
            f"{API_PREFIX}/documents/resumes/{document_a_id}/enhance",
            json={"resume_text": original_rendered},
        )

    assert enhance_response.status_code == 200, enhance_response.text

    # --- ШАГ 3: проверки ---
    result = enhance_response.json()
    document_b_id = result["document_id"]

    # document B имеет новый ID
    assert document_b_id != document_a_id

    # Получаем document B через API
    doc_b_response = await client.get(f"{API_PREFIX}/documents/{document_b_id}")
    assert doc_b_response.status_code == 200
    document_b = doc_b_response.json()

    # Проверка версии
    assert document_b["version_label"] == "resume_enhanced_v1"
    assert document_b["review_status"] == "draft"

    # Проверка через БД что derived_from_id = document_a_id
    stmt = select(DocumentVersion).where(DocumentVersion.id == document_b_id)
    doc_b_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert doc_b_db is not None
    assert str(doc_b_db.derived_from_id) == document_a_id

    # Проверка что document_a не изменился
    stmt = select(DocumentVersion).where(DocumentVersion.id == document_a_id)
    doc_a_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert doc_a_db is not None
    assert doc_a_db.derived_from_id is None

    # Проверка метаданных
    assert doc_b_db.content_json is not None
    assert doc_b_db.content_json["meta"]["enhanced_from"] == document_a_id
    assert "diff_from_previous" in doc_b_db.content_json["meta"]


@pytest.mark.asyncio
async def test_enhance_preserves_original_document(client):
    """Тест что оригинальный документ не изменяется после enhance."""
    from app.repositories.document_version_repository import DocumentVersionRepository
    from app.ai.orchestrator import AIOrchestrator
    from unittest.mock import AsyncMock, patch

    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    repo = DocumentVersionRepository()

    # Генерируем резюме
    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert generate_response.status_code == 200
    document_a_id = generate_response.json()["document_id"]

    doc_a_response = await client.get(f"{API_PREFIX}/documents/{document_a_id}")
    document_a = doc_a_response.json()
    original_rendered = document_a["rendered_text"]

    # Enhance с mock
    with patch.object(AIOrchestrator, '__init__', lambda self, client: None), \
         patch.object(AIOrchestrator, 'execute', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = {
            "result": {"enhanced_text": "Enhanced: " + original_rendered}
        }

        enhance_response = await client.post(
            f"{API_PREFIX}/documents/resumes/{document_a_id}/enhance",
            json={"resume_text": original_rendered},
        )

    assert enhance_response.status_code == 200

    # Перечитаем document_a через API чтобы убедиться что он не изменился
    doc_a_fresh_response = await client.get(f"{API_PREFIX}/documents/{document_a_id}")
    doc_a_fresh = doc_a_fresh_response.json()

    assert doc_a_fresh["rendered_text"] == original_rendered
    assert doc_a_fresh["version_label"] == "resume_draft_v2_review_ready"


@pytest.mark.asyncio
async def test_document_history_shows_all_versions(client, db_session):
    """Тест что history возвращает все версии документа в правильном порядке."""
    from sqlalchemy import select
    from app.models.entities import DocumentVersion
    from app.ai.orchestrator import AIOrchestrator
    from unittest.mock import AsyncMock, patch

    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    # --- ШАГ 1: generate → A ---
    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert generate_response.status_code == 200
    document_a_id = generate_response.json()["document_id"]

    doc_a_response = await client.get(f"{API_PREFIX}/documents/{document_a_id}")
    document_a = doc_a_response.json()
    original_rendered = document_a["rendered_text"]

    # --- ШАГ 2: enhance → B ---
    with patch.object(AIOrchestrator, '__init__', lambda self, client: None), \
         patch.object(AIOrchestrator, 'execute', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = {
            "result": {"enhanced_text": "Enhanced v1: " + original_rendered}
        }

        enhance_b_response = await client.post(
            f"{API_PREFIX}/documents/resumes/{document_a_id}/enhance",
            json={"resume_text": original_rendered},
        )
    assert enhance_b_response.status_code == 200
    document_b_id = enhance_b_response.json()["document_id"]

    # --- ШАГ 3: enhance → C ---
    doc_b_response = await client.get(f"{API_PREFIX}/documents/{document_b_id}")
    document_b = doc_b_response.json()

    with patch.object(AIOrchestrator, '__init__', lambda self, client: None), \
         patch.object(AIOrchestrator, 'execute', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = {
            "result": {"enhanced_text": "Enhanced v2: " + original_rendered}
        }

        enhance_c_response = await client.post(
            f"{API_PREFIX}/documents/resumes/{document_b_id}/enhance",
            json={"resume_text": document_b["rendered_text"]},
        )
    assert enhance_c_response.status_code == 200
    document_c_id = enhance_c_response.json()["document_id"]

    # --- ШАГ 4: проверяем history ---
    history_response = await client.get(f"{API_PREFIX}/documents/{document_a_id}/history")
    assert history_response.status_code == 200
    history = history_response.json()

    assert len(history["items"]) == 3

    # Порядок: C, B, A (новые первыми)
    assert history["items"][0]["id"] == document_c_id
    assert history["items"][0]["derived_from_id"] == document_b_id
    assert history["items"][0]["is_active"] is False
    assert history["items"][0]["review_status"] == "draft"

    assert history["items"][1]["id"] == document_b_id
    assert history["items"][1]["derived_from_id"] == document_a_id
    assert history["items"][1]["is_active"] is False
    assert history["items"][1]["review_status"] == "draft"

    # A теряет is_active=True когда создана новая версия через enhance
    # (deactivate_same_scope деактивирует предыдущие версии)
    assert history["items"][2]["id"] == document_a_id
    assert history["items"][2]["derived_from_id"] is None
    assert history["items"][2]["is_active"] is False
    assert history["items"][2]["review_status"] == "draft"
