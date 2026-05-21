from __future__ import annotations

import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _upload_file(
    client,
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> tuple[int, dict]:
    response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": (filename, content, content_type)},
    )
    return response.status_code, response.json()


async def test_file_upload_rejects_oversized_file(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "5")
    get_settings.cache_clear()

    try:
        status_code, payload = await _upload_file(
            client,
            filename="resume.pdf",
            content=b"123456",
            content_type="application/pdf",
        )

        assert status_code == 413
        assert payload["error"]["code"] == "upload_file_too_large"
        assert payload["error"]["message"] == "Uploaded file is too large"
    finally:
        get_settings.cache_clear()


async def test_file_upload_rejects_forbidden_extension(client):
    status_code, payload = await _upload_file(
        client,
        filename="resume.exe",
        content=b"MZ fake binary",
        content_type="application/octet-stream",
    )

    assert status_code == 400
    assert payload["error"]["code"] == "unsupported_file_extension"
    assert payload["error"]["message"] == "Unsupported file extension"
