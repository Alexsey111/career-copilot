from __future__ import annotations

import pytest

from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository


API_PREFIX = "/api/v1"
pytestmark = pytest.mark.asyncio


async def test_resume_upload_reuses_duplicate_content_and_keeps_active_resume(
    client,
    db_session,
    test_user,
) -> None:
    first = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume-v1.pdf", b"%PDF duplicate content", "application/pdf")},
    )
    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert first_payload["lifecycle_status"] == "active"
    assert first_payload["content_sha256"]

    second = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume-copy.pdf", b"%PDF duplicate content", "application/pdf")},
    )
    assert second.status_code == 200, second.text
    second_payload = second.json()

    assert second_payload["id"] == first_payload["id"]
    assert second_payload["content_sha256"] == first_payload["content_sha256"]
    assert second_payload["lifecycle_status"] == "active"

    active = await client.get(f"{API_PREFIX}/files/resume/active")
    assert active.status_code == 200, active.text
    assert active.json()["id"] == first_payload["id"]

    repo = SourceFileRepository()
    active_source = await repo.get_active_by_kind(
        db_session,
        user_id=test_user.id,
        file_kind="resume",
    )
    assert active_source is not None
    assert str(active_source.id) == first_payload["id"]


async def test_new_resume_supersedes_old_without_deleting_lineage(
    client,
    db_session,
    test_user,
) -> None:
    first = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume-v1.pdf", b"%PDF old resume", "application/pdf")},
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume-v2.pdf", b"%PDF new resume", "application/pdf")},
    )
    assert second.status_code == 200, second.text

    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["id"] != second_payload["id"]
    assert second_payload["lifecycle_status"] == "active"

    repo = SourceFileRepository()
    old_source = await repo.get_by_id(
        db_session,
        first_payload["id"],
        user_id=test_user.id,
    )
    assert old_source is not None
    assert old_source.lifecycle_status == "superseded"
    assert str(old_source.superseded_by_id) == second_payload["id"]

    active = await client.get(f"{API_PREFIX}/files/resume/active")
    assert active.status_code == 200, active.text
    assert active.json()["id"] == second_payload["id"]


async def test_duplicate_resume_import_reuses_existing_extraction(client, db_session) -> None:
    upload = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF same import", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    source_file_id = upload.json()["id"]

    first_import = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert first_import.status_code == 200, first_import.text

    second_import = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert second_import.status_code == 200, second_import.text
    assert second_import.json()["extraction_id"] == first_import.json()["extraction_id"]

    extraction_repo = FileExtractionRepository()
    latest = await extraction_repo.get_latest_for_source_file(
        db_session,
        source_file_id=source_file_id,
    )
    assert latest is not None
    assert str(latest.id) == first_import.json()["extraction_id"]
