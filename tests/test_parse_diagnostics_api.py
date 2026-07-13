from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_parse_diagnostics_returns_report_for_imported_resume(
    client: AsyncClient,
) -> None:
    """Этап 8: импорт резюме → POST /profile/parse-diagnostics → отчёт с блоками."""
    upload = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python, FastAPI, Docker", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    source_file_id = upload.json()["id"]

    import_resp = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_resp.status_code == 200, import_resp.text

    diag = await client.post(
        f"{API_PREFIX}/profile/parse-diagnostics",
        json={"source_file_id": source_file_id},
    )
    assert diag.status_code == 200, diag.text
    body = diag.json()

    assert body["detected_format"] in {"pdf", "docx", "txt", "text"}
    assert isinstance(body["extracted_blocks"], list)
    assert isinstance(body["block_order"], list)
    assert isinstance(body["lost_blocks"], list)
    assert isinstance(body["structural_warnings"], list)
    assert isinstance(body["hidden_text_findings"], list)
    assert "file_metadata" in body
    assert "metadata_exposure_warning" in body


async def test_parse_diagnostics_404_for_unknown_source_file(
    client: AsyncClient,
) -> None:
    import uuid

    diag = await client.post(
        f"{API_PREFIX}/profile/parse-diagnostics",
        json={"source_file_id": str(uuid.uuid4())},
    )
    assert diag.status_code == 404
    assert diag.json()["detail"] == "source file not found"


async def test_parse_diagnostics_400_for_non_resume_file(client: AsyncClient) -> None:
    """Вакансия — не resume file_kind → 400."""
    upload = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "vacancy"},
        files={
            "file": (
                "vacancy.txt",
                b"Python developer wanted. Experience with FastAPI required.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    source_file_id = upload.json()["id"]

    diag = await client.post(
        f"{API_PREFIX}/profile/parse-diagnostics",
        json={"source_file_id": source_file_id},
    )
    assert diag.status_code == 400
    assert diag.json()["detail"] == "source file is not a resume"


async def test_parse_diagnostics_404_when_no_extraction(client: AsyncClient) -> None:
    """Резюме загружено, но не импортировано → нет extraction → 404."""
    upload = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python, Docker", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    source_file_id = upload.json()["id"]

    diag = await client.post(
        f"{API_PREFIX}/profile/parse-diagnostics",
        json={"source_file_id": source_file_id},
    )
    assert diag.status_code == 404
    assert diag.json()["detail"] == "no extraction found; import the resume first"