from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.resume_parser_service import ResumeParserService


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_vacancy_import_from_file_smoke_upload_import_analyze(
    client,
    monkeypatch,
) -> None:
    vacancy_text = (
        "Требования:\n"
        "- Python\n"
        "- FastAPI\n"
        "- PostgreSQL\n"
        "\n"
        "Будет плюсом:\n"
        "- Redis\n"
        "- Docker\n"
        "\n"
        "Условия:\n"
        "- Удаленная работа\n"
    )

    def parse(self, *, file_bytes: bytes, mime_type: str | None, filename: str):
        return SimpleNamespace(
            text=file_bytes.decode("utf-8"),
            metadata={
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(file_bytes),
            },
            detected_format="txt",
        )

    monkeypatch.setattr(ResumeParserService, "parse", parse)

    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "vacancy"},
        files={
            "file": (
                "vacancy.txt",
                vacancy_text.encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/vacancies/import-from-file",
        json={
            "source_file_id": source_file_id,
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
        },
    )
    assert import_response.status_code == 200, import_response.text
    imported = import_response.json()

    assert imported["source"] == "file"
    assert imported["title"] == "Backend Developer"
    assert imported["company"] == "Test Company"
    normalized_text = "\n".join(
        line.strip()
        for line in vacancy_text.splitlines()
        if line.strip()
    )
    assert imported["description_length"] == len(normalized_text)

    vacancy_id = imported["vacancy_id"]
    analysis_response = await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze",
    )
    assert analysis_response.status_code == 200, analysis_response.text
    analysis = analysis_response.json()

    assert [item["text"] for item in analysis["must_have"]] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]
    assert [item["text"] for item in analysis["nice_to_have"]] == [
        "Redis",
        "Docker",
    ]
    assert analysis["keywords"] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Redis",
        "Docker",
    ]
