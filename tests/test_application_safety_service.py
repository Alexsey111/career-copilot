from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.application_safety_service import ApplicationSafetyService


class StubDocumentVersionRepository:
    def __init__(self, document=None) -> None:
        self.document = document

    async def get_active_for_scope(
        self,
        session,
        *,
        user_id,
        vacancy_id,
        document_kind,
    ):
        return self.document


def _build_document(
    *,
    review_status: str = "approved",
    is_active: bool = True,
    content_json: dict | None = None,
):
    return SimpleNamespace(
        id=uuid4(),
        review_status=review_status,
        is_active=is_active,
        content_json=content_json or {},
    )


@pytest.mark.asyncio
async def test_can_apply_allows_ready_active_resume_document():
    document = _build_document(
        content_json={
            "sections": {
                "claims_needing_confirmation": [],
                "selected_achievements": [{"metric_text": "Increased pipeline throughput by 30%"}],
            },
            "evaluation": {
                "critical_failures": [],
                "coverage_gaps": [],
            },
            "review": {
                "latest_status": "approved",
            },
            "readiness_score": {
                "overall_score": 0.88,
                "ats_score": 0.83,
            },
        }
    )
    service = ApplicationSafetyService(
        document_version_repository=StubDocumentVersionRepository(document),
    )

    result = await service.can_apply(
        None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
    )

    assert result.allowed is True
    assert result.blockers == []
    assert result.warnings == []
    assert result.score == 0.88
    assert result.document_id == document.id


@pytest.mark.asyncio
async def test_can_apply_rejects_when_no_active_resume_document():
    service = ApplicationSafetyService(
        document_version_repository=StubDocumentVersionRepository(None),
    )

    result = await service.can_apply(
        None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
    )

    assert result.allowed is False
    assert result.blockers == ["active resume document not found"]
    assert result.document_id is None


@pytest.mark.asyncio
async def test_can_apply_rejects_when_human_review_is_not_approved():
    document = _build_document(
        content_json={
            "sections": {
                "claims_needing_confirmation": [],
                "selected_achievements": [{"metric_text": "Cut cloud spend by 18%"}],
            },
            "evaluation": {
                "critical_failures": [],
            },
            "review": {
                "latest_status": "changes_requested",
            },
        }
    )
    service = ApplicationSafetyService(
        document_version_repository=StubDocumentVersionRepository(document),
    )

    result = await service.can_apply(
        None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
    )

    assert result.allowed is False
    assert "document review is not approved by human review" in result.blockers


@pytest.mark.asyncio
async def test_can_apply_rejects_when_claims_are_unresolved():
    document = _build_document(
        content_json={
            "sections": {
                "claims_needing_confirmation": [{"claim_text": "Managed $2M budget"}],
            },
            "evaluation": {
                "critical_failures": [],
            },
            "review": {
                "latest_status": "approved",
            },
        }
    )
    service = ApplicationSafetyService(
        document_version_repository=StubDocumentVersionRepository(document),
    )

    result = await service.can_apply(
        None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
    )

    assert result.allowed is False
    assert result.blockers.count(
        "document has unresolved claims requiring confirmation"
    ) == 1
