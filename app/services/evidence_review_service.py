# app\services\evidence_review_service.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvidenceSnippet
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository


class EvidenceReviewService:
    def __init__(
        self,
        evidence_repository: EvidenceSnippetRepository | None = None,
    ) -> None:
        self.evidence_repository = evidence_repository or EvidenceSnippetRepository()

    async def confirm(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        snippet_id: UUID,
    ) -> EvidenceSnippet | None:
        snippet = await self.evidence_repository.get_by_id_for_user(
            session,
            user_id=user_id,
            snippet_id=snippet_id,
        )
        if snippet is None:
            return None

        snippet.fact_status = "confirmed"
        snippet.evidence_strength = self._promoted_strength(snippet)
        await session.flush()
        await session.refresh(snippet)
        return snippet

    async def reject(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        snippet_id: UUID,
    ) -> EvidenceSnippet | None:
        snippet = await self.evidence_repository.get_by_id_for_user(
            session,
            user_id=user_id,
            snippet_id=snippet_id,
        )
        if snippet is None:
            return None

        snippet.fact_status = "rejected"
        await session.flush()
        await session.refresh(snippet)
        return snippet

    def _promoted_strength(self, snippet: EvidenceSnippet) -> str:
        strength = str(snippet.evidence_strength or "weak").strip().lower()
        source_type = str(snippet.source_type or "").strip().lower()

        if strength == "weak":
            return "medium"
        if strength == "medium" and source_type != "github_public":
            return "strong"
        return strength or "weak"
