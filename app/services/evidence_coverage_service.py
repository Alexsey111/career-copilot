from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository


class EvidenceCoverageService:
    """Deterministic evidence coverage trends for reusable snippets."""

    def __init__(self, repository: EvidenceSnippetRepository | None = None) -> None:
        self.repository = repository or EvidenceSnippetRepository()

    async def build_coverage_trends(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        snippets = await self.repository.list_by_user_id(session, user_id=user_id)
        if not snippets:
            return {
                "most_reusable_evidence": [],
                "unused_evidence": [],
                "weak_evidence_clusters": [],
            }

        most_reusable = sorted(
            snippets,
            key=lambda item: (
                int(item.usage_count or 0),
                int(item.used_in_documents_count or 0),
                int(item.used_in_interviews_count or 0),
                str(item.evidence_strength or ""),
            ),
            reverse=True,
        )[:5]

        unused = [item for item in snippets if int(item.usage_count or 0) == 0][:5]

        cluster_counts: Counter[str] = Counter()
        cluster_titles: dict[str, set[str]] = defaultdict(set)
        for snippet in snippets:
            strength = str(snippet.evidence_strength or "weak").strip().lower()
            if strength not in {"weak", "medium"}:
                continue
            for skill in snippet.skills_json or []:
                label = str(skill).strip()
                if not label:
                    continue
                cluster_counts[label] += 1
                cluster_titles[label].add(str(snippet.title or "Evidence snippet"))

        weak_clusters = []
        for skill, count in cluster_counts.most_common():
            weak_clusters.append(
                {
                    "skill": skill,
                    "count": count,
                    "example_evidence_titles": sorted(cluster_titles.get(skill, set()))[:3],
                }
            )

        return {
            "most_reusable_evidence": [
                self._snippet_to_item(item) for item in most_reusable
            ],
            "unused_evidence": [
                self._snippet_to_item(item) for item in unused
            ],
            "weak_evidence_clusters": weak_clusters[:10],
        }

    def _snippet_to_item(self, snippet) -> dict[str, Any]:
        return {
            "evidence_id": getattr(snippet, "id", None),
            "title": getattr(snippet, "title", None) or "Evidence snippet",
            "evidence_strength": getattr(snippet, "evidence_strength", None) or "weak",
            "fact_status": getattr(snippet, "fact_status", None) or "unverified",
            "usage_count": int(getattr(snippet, "usage_count", 0) or 0),
            "used_in_documents_count": int(getattr(snippet, "used_in_documents_count", 0) or 0),
            "used_in_interviews_count": int(getattr(snippet, "used_in_interviews_count", 0) or 0),
            "reason": self._reason(snippet),
        }

    def _reason(self, snippet) -> str:
        usage_count = int(getattr(snippet, "usage_count", 0) or 0)
        strength = str(getattr(snippet, "evidence_strength", "") or "weak").strip().lower()
        fact_status = str(getattr(snippet, "fact_status", "") or "unverified").strip().lower()
        if usage_count == 0:
            return "Unused evidence is available for reuse."
        if strength == "strong" and fact_status == "confirmed":
            return "Strong confirmed evidence with a reusable track record."
        if strength == "medium":
            return "Moderate evidence that may become stronger with more metrics."
        return "Evidence exists but still needs strengthening or confirmation."
