from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import DocumentVersion

pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_activate_requires_approved_document(client):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )

    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )

    vacancy_id = vacancy_response.json()["vacancy_id"]

    await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze"
    )

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_id = generate_response.json()["document_id"]

    activate_response = await client.post(
        f"{API_PREFIX}/documents/{document_id}/activate"
    )

    assert activate_response.status_code == 409
    assert (
        activate_response.json()["detail"]
        == "only approved documents can be activated"
    )


async def test_activate_sets_document_active(client):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )

    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )

    vacancy_id = vacancy_response.json()["vacancy_id"]

    await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze"
    )

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_id = generate_response.json()["document_id"]

    review_response = await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    assert review_response.status_code == 200

    activate_response = await client.post(
        f"{API_PREFIX}/documents/{document_id}/activate"
    )

    assert activate_response.status_code == 200

    data = activate_response.json()

    assert data["document_id"] == document_id
    assert data["is_active"] is True


async def test_activate_approved_document_without_blockers_succeeds(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {"claims_needing_confirmation": []}
    content["evaluation"] = {"critical_failures": []}
    content["review"] = {"latest_status": "approved"}
    document.content_json = content
    await db_session.commit()

    activate_response = await client.post(f"{API_PREFIX}/documents/{document_id}/activate")

    assert activate_response.status_code == 200, activate_response.text
    assert activate_response.json()["is_active"] is True


async def test_activate_rejects_document_with_unresolved_claims(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {"claims_needing_confirmation": [{"claim_text": "Need proof"}]}
    document.content_json = content
    await db_session.commit()

    activate_response = await client.post(f"{API_PREFIX}/documents/{document_id}/activate")

    assert activate_response.status_code == 409, activate_response.text
    assert activate_response.json()["detail"] == "document has unresolved claims requiring confirmation"


async def test_activate_rejects_document_with_critical_failures(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["evaluation"] = {"critical_failures": [{"code": "missing_evidence"}]}
    document.content_json = content
    await db_session.commit()

    activate_response = await client.post(f"{API_PREFIX}/documents/{document_id}/activate")

    assert activate_response.status_code == 409, activate_response.text
    assert activate_response.json()["detail"] == "document has unresolved critical evaluation failures"


async def test_activate_rejects_document_with_non_approved_review_latest_status(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["review"] = {"latest_status": "review_required"}
    document.content_json = content
    await db_session.commit()

    activate_response = await client.post(f"{API_PREFIX}/documents/{document_id}/activate")

    assert activate_response.status_code == 409, activate_response.text
    assert activate_response.json()["detail"] == "document review is not approved"


async def test_get_document_readiness_returns_ready_state(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )
    await client.post(f"{API_PREFIX}/documents/{document_id}/activate")

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {
        "claims_needing_confirmation": [],
        "selected_achievements": [{"metric_text": "Reduced latency by 20%"}],
    }
    content["evaluation"] = {"critical_failures": [], "coverage_gaps": []}
    content["review"] = {"latest_status": "approved"}
    content["readiness_score"] = {"overall_score": 0.84, "ats_score": 0.82}
    document.content_json = content
    await db_session.commit()

    readiness_response = await client.get(f"{API_PREFIX}/documents/{document_id}/readiness")

    assert readiness_response.status_code == 200, readiness_response.text
    payload = readiness_response.json()
    assert payload["ready"] is True
    assert payload["blockers"] == []
    assert payload["warnings"] == []
    assert payload["score"] == 0.84


async def test_get_document_readiness_returns_blockers_and_warnings(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {
        "claims_needing_confirmation": [{"claim_text": "Need proof"}],
        "selected_achievements": [{"metric_text": ""}],
    }
    content["evaluation"] = {
        "critical_failures": [{"code": "missing_evidence"}],
        "coverage_gaps": [{"requirement": "Docker"}],
    }
    content["readiness_score"] = {"overall_score": 0.58, "ats_score": 0.55}
    document.content_json = content
    await db_session.commit()

    readiness_response = await client.get(f"{API_PREFIX}/documents/{document_id}/readiness")

    assert readiness_response.status_code == 200, readiness_response.text
    payload = readiness_response.json()
    assert payload["ready"] is False
    assert "статус проверки документа не «одобрен»" in payload["blockers"]
    assert "в документе есть утверждения, требующие подтверждения" in payload["blockers"]
    assert "в документе есть нерешённые критические ошибки оценки" in payload["blockers"]
    assert "документ неактивен" in payload["blockers"]
    assert "в документе есть пробелы в покрытии требований" in payload["warnings"]
    assert "низкий ATS-балл документа (0.55)" in payload["warnings"]
    assert "в документе есть достижения без метрик" in payload["warnings"]
    assert payload["score"] == 0.58


async def test_get_document_readiness_returns_404_for_missing_document(client):
    readiness_response = await client.get(f"{API_PREFIX}/documents/{UUID(int=0)}/readiness")

    assert readiness_response.status_code == 404, readiness_response.text
    assert readiness_response.json()["detail"] == "document not found"


async def test_get_document_review_summary_returns_sections_and_readiness(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )
    await client.post(f"{API_PREFIX}/documents/{document_id}/activate")

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {
        "claims_needing_confirmation": [],
        "warnings": [{"code": "ats_plaintext_draft"}],
        "selected_achievements": [{"title": "Shipped feature", "metric_text": "20%"}],
        "matched_keywords": ["Python", "FastAPI"],
        "missing_keywords": ["Redis"],
        "selection_rationale": [{"item": "Python", "type": "skill", "reason": "vacancy_overlap"}],
    }
    content["evaluation"] = {"critical_failures": [], "coverage_gaps": []}
    content["review"] = {"latest_status": "approved"}
    content["readiness_score"] = {"overall_score": 0.91, "ats_score": 0.88}
    document.content_json = content
    await db_session.commit()

    summary_response = await client.get(
        f"{API_PREFIX}/documents/{document_id}/review-summary"
    )

    assert summary_response.status_code == 200, summary_response.text
    payload = summary_response.json()
    assert payload["document_id"] == document_id
    assert payload["document_kind"] == "resume"
    assert payload["review_status"] == "approved"
    assert payload["is_active"] is True
    assert payload["readiness"]["ready"] is True
    assert payload["claims_needing_confirmation"] == []
    assert payload["warnings"] == [{"code": "ats_plaintext_draft"}]
    assert payload["selected_achievements"][0]["title"] == "Shipped feature"
    assert "selected_evidence_ids" in payload
    assert isinstance(payload["selected_evidence_ids"], list)
    assert "selected_achievement_ids" in payload
    assert isinstance(payload["selected_achievement_ids"], list)
    assert "evidence_selection_reason" in payload
    assert isinstance(payload["evidence_selection_reason"], list)
    assert payload["provenance"]["requires_human_review"] is True
    assert payload["provenance"]["selected_evidence_ids"]
    assert "quality" in payload
    assert isinstance(payload["quality"], dict)
    assert payload["matched_keywords"] == ["Python", "FastAPI"]
    assert payload["missing_keywords"] == ["Redis"]
    assert payload["selection_rationale"][0]["reason"] == "vacancy_overlap"
    assert payload["rendered_text_preview"]


async def test_review_document_rejects_approval_when_not_ready(client, db_session):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )
    vacancy_id = vacancy_response.json()["vacancy_id"]
    await client.post(f"{API_PREFIX}/vacancies/{vacancy_id}/analyze")

    generate_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    document_id = generate_response.json()["document_id"]

    document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == UUID(document_id))
        )
    ).scalar_one()
    content = dict(document.content_json or {})
    content["sections"] = {
        "claims_needing_confirmation": [{"text": "Need proof"}],
        "selected_achievements": [{"title": "Shipped feature", "metric_text": "20%"}],
        "warnings": [],
        "matched_keywords": ["Python"],
        "missing_keywords": [],
        "selection_rationale": [],
    }
    content["evaluation"] = {"critical_failures": [], "coverage_gaps": []}
    document.content_json = content
    await db_session.commit()

    review_response = await client.patch(
        f"{API_PREFIX}/documents/{document_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approve while not ready",
            "set_active_when_approved": False,
        },
    )

    assert review_response.status_code == 409, review_response.text
    detail = review_response.json()["detail"]
    assert detail["message"] == "document is not ready for approval"
    assert "в документе есть утверждения, требующие подтверждения" in detail["readiness"]["blockers"]
    assert detail["readiness"]["ready"] is False
async def test_activate_deactivates_previous_active_document(client):
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", b"Python FastAPI", "text/plain")},
    )
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    extraction_id = import_response.json()["extraction_id"]

    await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )

    await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test",
            "location": "Remote",
            "description_raw": "Python FastAPI PostgreSQL",
        },
    )

    vacancy_id = vacancy_response.json()["vacancy_id"]

    await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze"
    )

    # Generate resume_v1
    generate_v1_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_v1_id = generate_v1_response.json()["document_id"]

    # Approve resume_v1
    await client.patch(
        f"{API_PREFIX}/documents/{document_v1_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": True,
        },
    )

    # Verify resume_v1 is active
    get_v1_response = await client.get(
        f"{API_PREFIX}/documents/{document_v1_id}"
    )
    assert get_v1_response.json()["is_active"] is True

    # Generate resume_v2
    generate_v2_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )

    document_v2_id = generate_v2_response.json()["document_id"]

    # Approve resume_v2
    await client.patch(
        f"{API_PREFIX}/documents/{document_v2_id}/review",
        json={
            "review_status": "approved",
            "review_comment": "approved",
            "set_active_when_approved": False,
        },
    )

    # Activate resume_v2
    activate_v2_response = await client.post(
        f"{API_PREFIX}/documents/{document_v2_id}/activate"
    )

    assert activate_v2_response.status_code == 200

    # Verify resume_v1 is now inactive
    get_v1_response = await client.get(
        f"{API_PREFIX}/documents/{document_v1_id}"
    )
    assert get_v1_response.json()["is_active"] is False

    # Verify resume_v2 is now active
    get_v2_response = await client.get(
        f"{API_PREFIX}/documents/{document_v2_id}"
    )
    assert get_v2_response.json()["is_active"] is True
