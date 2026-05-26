# app\services\evidence_bank_service.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.evidence import EvidenceSourceType
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.services.evidence_extraction_service import EvidenceExtractionService


EVIDENCE_BANK_SOURCE_TYPES = [
    EvidenceSourceType.ACHIEVEMENT.value,
    EvidenceSourceType.RESUME_STRUCTURED.value,
    EvidenceSourceType.RESUME.value,
    EvidenceSourceType.GITHUB_PUBLIC.value,
    EvidenceSourceType.MANUAL.value,
    EvidenceSourceType.INTERVIEW.value,
]

PROJECT_EVIDENCE_CATEGORIES = {
    "project",
    "ai_project",
    "automation",
    "prompt_engineering",
    "internship",
    "achievement",
}
COMPETENCY_SIGNAL_CATEGORIES = {
    "competency_signal",
    "workflow_experience",
    "technologies",
}


@dataclass(frozen=True)
class EvidenceBankItem:
    id: str
    title: str
    snippet_text: str
    source_type: str
    skills: list[str] = field(default_factory=list)
    evidence_strength: str = "weak"
    fact_status: str = "unverified"
    usage_count: int = 0
    used_in_documents_count: int = 0
    used_in_interviews_count: int = 0
    category: str | None = None
    star_summary: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "snippet_text": self.snippet_text,
            "source_type": self.source_type,
            "skills": list(self.skills),
            "evidence_strength": self.evidence_strength,
            "fact_status": self.fact_status,
            "usage_count": self.usage_count,
            "used_in_documents_count": self.used_in_documents_count,
            "used_in_interviews_count": self.used_in_interviews_count,
            "category": self.category,
            "star_summary": dict(self.star_summary),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class AchievementEvidence(EvidenceBankItem):
    pass


@dataclass(frozen=True)
class CompetencySignal(EvidenceBankItem):
    pass


@dataclass(frozen=True)
class ProjectEvidence(EvidenceBankItem):
    pass


@dataclass(frozen=True)
class EvidenceBankSnapshot:
    snippets: list[EvidenceBankItem] = field(default_factory=list)
    achievements: list[AchievementEvidence] = field(default_factory=list)
    competency_signals: list[CompetencySignal] = field(default_factory=list)
    project_evidence: list[ProjectEvidence] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "snippets": [item.as_dict() for item in self.snippets],
            "achievements": [item.as_dict() for item in self.achievements],
            "competency_signals": [item.as_dict() for item in self.competency_signals],
            "project_evidence": [item.as_dict() for item in self.project_evidence],
        }


class EvidenceBankService:
    def __init__(
        self,
        *,
        repository: EvidenceSnippetRepository | None = None,
        extraction_service: EvidenceExtractionService | None = None,
    ) -> None:
        self.repository = repository or EvidenceSnippetRepository()
        self.extraction_service = extraction_service or EvidenceExtractionService()

    async def build_bank(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        achievements: Sequence[Mapping[str, Any]] | None = None,
    ) -> EvidenceBankSnapshot:
        if achievements:
            await self.upsert_achievement_evidence(
                session,
                user_id=user_id,
                achievements=achievements,
            )

        snippets = await self.repository.list_by_user_id(
            session,
            user_id=user_id,
            source_types=EVIDENCE_BANK_SOURCE_TYPES,
        )
        items = [self._model_to_item(snippet) for snippet in snippets]

        return EvidenceBankSnapshot(
            snippets=items,
            achievements=[
                AchievementEvidence(**item.as_dict())
                for item in items
                if self._is_achievement(item)
            ],
            competency_signals=[
                CompetencySignal(**item.as_dict())
                for item in items
                if self._is_competency_signal(item)
            ],
            project_evidence=[
                ProjectEvidence(**item.as_dict())
                for item in items
                if self._is_project_evidence(item)
            ],
        )

    async def upsert_achievement_evidence(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        achievements: Sequence[Mapping[str, Any]],
    ) -> None:
        drafts = self.extraction_service.extract_from_achievements(
            list(achievements),
            user_id=str(user_id),
            source_type=EvidenceSourceType.ACHIEVEMENT,
        )
        await self.repository.upsert_many(
            session,
            user_id=user_id,
            snippets=[self.extraction_service.snippet_to_dict(snippet) for snippet in drafts],
        )

    def _model_to_item(self, snippet) -> EvidenceBankItem:
        star_summary = dict(getattr(snippet, "star_summary_json", None) or {})
        category = str(star_summary.get("category") or "").strip() or None
        return EvidenceBankItem(
            id=str(snippet.id),
            title=str(snippet.title or ""),
            snippet_text=str(snippet.snippet_text or ""),
            source_type=str(snippet.source_type or "").strip().lower(),
            skills=list(snippet.skills_json or []),
            evidence_strength=str(snippet.evidence_strength or "weak").strip().lower(),
            fact_status=str(snippet.fact_status or "unverified").strip().lower(),
            usage_count=int(snippet.usage_count or 0),
            used_in_documents_count=int(snippet.used_in_documents_count or 0),
            used_in_interviews_count=int(snippet.used_in_interviews_count or 0),
            category=category,
            star_summary=star_summary,
            created_at=getattr(snippet, "created_at", None),
            updated_at=getattr(snippet, "updated_at", None),
        )

    def _is_achievement(self, item: EvidenceBankItem) -> bool:
        return item.source_type == EvidenceSourceType.ACHIEVEMENT.value

    def _is_competency_signal(self, item: EvidenceBankItem) -> bool:
        return item.category in COMPETENCY_SIGNAL_CATEGORIES

    def _is_project_evidence(self, item: EvidenceBankItem) -> bool:
        return item.category in PROJECT_EVIDENCE_CATEGORIES
