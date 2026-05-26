from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.exceptions import AppError
from app.main import app
from app.repositories.document_version_repository import DocumentVersionRepository


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _seed_draft_document(db_session, test_user):
    repo = DocumentVersionRepository()
    document = await repo.create(
        db_session,
        user_id=test_user.id,
        vacancy_id=None,
        derived_from_id=None,
        analysis_id=None,
        document_kind="resume",
        version_label="resume_draft_contract_check",
        review_status="draft",
        is_active=False,
        content_json={"meta": {}, "sections": {}},
        rendered_text="Draft resume",
    )
    await db_session.commit()
    return document


async def _create_resume_document(client) -> str:
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python, FastAPI, Docker", "text/plain")},
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

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "description_raw": (
                "Requirements:\n"
                "- Python\n"
                "- FastAPI\n"
                "- PostgreSQL\n"
            ),
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy_id = vacancy_response.json()["vacancy_id"]

    analysis_response = await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")
    assert analysis_response.status_code == 200, analysis_response.text

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    return resume_response.json()["document_id"]


async def test_app_error_uses_stable_code_and_detail(client) -> None:
    response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "invalid"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
    )

    assert response.status_code == 400, response.text
    body = response.json()

    assert body["detail"] == {
        "allowed_file_kinds": ["other", "resume", "vacancy"],
    }
    assert body["error"]["code"] == "invalid_file_kind"
    assert body["error"]["message"] == "file_kind must be one of: ['other', 'resume', 'vacancy']"
    assert body["error"]["correlation_id"]
    assert body["error"]["details"] == {
        "allowed_file_kinds": ["other", "resume", "vacancy"],
    }


async def test_not_found_error_is_deterministic(client) -> None:
    response = await client.get(f"{API_PREFIX}/documents/{UUID(int=0)}")

    assert response.status_code == 404, response.text
    body = response.json()

    assert body["detail"] == "document not found"
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "document not found"
    assert body["error"]["details"] == {}


async def test_conflict_error_is_deterministic(client, db_session, test_user) -> None:
    resume_document_id = await _create_resume_document(client)

    response = await client.get(f"{API_PREFIX}/documents/{resume_document_id}/export/txt")

    assert response.status_code == 409, response.text
    body = response.json()

    assert body["detail"] == "document must be approved and active before export"
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "document must be approved and active before export"
    assert body["error"]["details"] == {}


async def test_validation_error_has_stable_shape(client) -> None:
    response = await client.post(f"{API_PREFIX}/auth/login", json={})

    assert response.status_code == 422, response.text
    body = response.json()

    assert body["detail"] == "Request validation failed"
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert "errors" in body["error"]["details"]
    assert body["error"]["details"]["errors"]
    first_error = body["error"]["details"]["errors"][0]
    assert {"type", "loc", "msg"}.issubset(first_error)


async def test_unhandled_exception_does_not_leak_stack_trace(client) -> None:
    route_path = "/api/v1/__contract__/boom-app-error"

    async def boom():
        raise AppError(
            code="internal_server_error",
            message="Internal server error",
            status_code=500,
        )

    app.add_api_route(route_path, boom, methods=["GET"])

    with TestClient(app, raise_server_exceptions=False) as isolated_client:
        response = isolated_client.get(route_path)

    assert response.status_code == 500, response.text
    body = response.json()

    assert body["detail"] == {}
    assert body["error"]["code"] == "internal_server_error"
    assert body["error"]["message"] == "Internal server error"
    assert body["error"]["details"] == {}
    assert "traceback" not in response.text.lower()
    assert "runtimeerror" not in response.text.lower()
