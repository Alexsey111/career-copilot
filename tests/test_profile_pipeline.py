from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceFile

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_resume_profile_pipeline_end_to_end(
    client,
    db_session: AsyncSession,
    test_user,
    fake_storage,
):
    source_file = SourceFile(
        user_id=test_user.id,
        file_kind="resume",
        storage_key="test/resume.pdf",
        original_name="resume.pdf",
        mime_type="application/pdf",
        size_bytes=123,
    )
    db_session.add(source_file)
    await db_session.commit()
    await db_session.refresh(source_file)

    fake_storage[source_file.storage_key] = b"fake pdf content"

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": str(source_file.id)},
    )

    assert import_response.status_code == 200
    import_data = import_response.json()

    assert import_data["status"] == "completed"
    assert import_data["detected_format"] == "pdf"
    assert import_data["text_length"] > 0
    assert import_data["extraction_id"]

    extraction_id = import_data["extraction_id"]

    structured_response = await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )

    assert structured_response.status_code == 200
    structured_data = structured_response.json()

    assert structured_data["profile_id"] == import_data["profile_id"]
    assert structured_data["full_name"] == "Алексей Перминов"
    assert structured_data["target_roles"]
    assert structured_data["experience_count"] >= 1
    assert structured_data["project_count"] >= 1
    assert structured_data["evidence_snippet_count"] >= 1
    assert "LLM" in structured_data["technologies"]
    assert structured_data["structured_evidence"]

    evidence_response = await client.get(f"{API_PREFIX}/evidence/snippets")
    assert evidence_response.status_code == 200, evidence_response.text
    evidence_payload = evidence_response.json()
    assert any(item["source_type"] == "resume_structured" for item in evidence_payload)
    assert any(
        item["star_summary"].get("source") == "structured_resume_extraction_v2"
        for item in evidence_payload
    )

    bank_response = await client.get(f"{API_PREFIX}/evidence/bank")
    assert bank_response.status_code == 200, bank_response.text
    bank_payload = bank_response.json()
    assert bank_payload["snippets"]
    assert bank_payload["project_evidence"]
    assert bank_payload["competency_signals"]

    achievements_response = await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    assert achievements_response.status_code == 200
    achievements_data = achievements_response.json()

    assert achievements_data["profile_id"] == import_data["profile_id"]
    assert achievements_data["achievement_count"] >= 1
    assert achievements_data["achievements"]

    first_achievement = achievements_data["achievements"][0]
    assert first_achievement["fact_status"] == "needs_confirmation"
