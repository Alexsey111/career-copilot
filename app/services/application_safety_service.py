from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_version_repository import DocumentVersionRepository
from app.services.readiness_gate_service import ReadinessGateService


@dataclass(slots=True)
class ApplicationSafetyResult:
    allowed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float | None = None
    document_id: UUID | None = None


class ApplicationSafetyService:
    """Operational safety gate before creating or submitting an application."""

    def __init__(
        self,
        document_version_repository: DocumentVersionRepository | None = None,
        readiness_gate_service: ReadinessGateService | None = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )
        self.readiness_gate_service = readiness_gate_service or ReadinessGateService()

    async def can_apply(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
    ) -> ApplicationSafetyResult:
        document = await self.document_version_repository.get_active_for_scope(
            session,
            user_id=user_id,
            vacancy_id=vacancy_id,
            document_kind="resume",
        )

        if document is None:
            return ApplicationSafetyResult(
                allowed=False,
                blockers=["active resume document not found"],
            )

        readiness = self.readiness_gate_service.evaluate_document_readiness(document)
        blockers = list(readiness.blockers)
        warnings = list(readiness.warnings)

        content = document.content_json or {}
        sections = content.get("sections", {})
        review = content.get("review", {})

        latest_status = review.get("latest_status")
        if latest_status and latest_status != "approved":
            detail = "document review is not approved by human review"
            if detail not in blockers:
                blockers.append(detail)

        unresolved_claims = sections.get("claims_needing_confirmation", [])
        if unresolved_claims:
            detail = "document has unresolved claims requiring confirmation"
            if detail not in blockers:
                blockers.append(detail)

        return ApplicationSafetyResult(
            allowed=readiness.ready and len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
            score=readiness.score,
            document_id=document.id,
        )
