from __future__ import annotations

import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _upload_file(client, *, filename: str, content: bytes, content_type: str, file_kind: str = "resume"):
    return await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": file_kind},
        files={"file": (filename, content, content_type)},
    )


async def test_file_upload_accepts_octet_stream_for_allowed_extension(client):
    response = await _upload_file(
        client,
        filename="resume.pdf",
        content=b"%PDF-1.4 fake pdf",
        content_type="application/octet-stream",
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["original_name"] == "resume.pdf"
    assert payload["mime_type"] == "application/octet-stream"


async def test_file_upload_rejects_unsupported_extension(client):
    response = await _upload_file(
        client,
        filename="resume.exe",
        content=b"MZ fake binary",
        content_type="application/octet-stream",
    )

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["error"]["code"] == "unsupported_file_extension"
    assert body["error"]["message"] == "Unsupported file extension"


async def test_file_upload_rejects_unsupported_content_type(client):
    response = await _upload_file(
        client,
        filename="resume.pdf",
        content=b"%PDF-1.4 fake pdf",
        content_type="application/x-msdownload",
    )

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["error"]["code"] == "unsupported_content_type"
    assert body["error"]["message"] == "Unsupported content type"


async def test_file_upload_enforces_configurable_size_limit(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "5")
    get_settings.cache_clear()

    try:
        response = await _upload_file(
            client,
            filename="resume.pdf",
            content=b"123456",
            content_type="application/pdf",
        )

        assert response.status_code == 413, response.text
        body = response.json()
        assert body["error"]["code"] == "upload_file_too_large"
        assert body["error"]["message"] == "Uploaded file is too large"
        assert body["error"]["details"]["max_upload_size_bytes"] == 5
    finally:
        get_settings.cache_clear()
