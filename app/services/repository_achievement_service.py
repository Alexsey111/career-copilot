# app\services\repository_achievement_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.services.core_service_policy import CORE_SERVICE_INVARIANT


@dataclass(frozen=True)
class RepositoryAchievementDraft:
    title: str
    skills: list[str]
    summary: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    fact_status: str = "needs_confirmation"
    candidate_ownership: str = "unknown"
    candidate_ownership_confidence: str = "low"
    requires_confirmation: bool = True
    repository_signal: bool = True
    source: str = "github_repository_analysis"
    source_evidence_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "skills": list(self.skills),
            "summary": self.summary,
            "situation": self.situation,
            "task": self.task,
            "action": self.action,
            "result": self.result,
            "fact_status": self.fact_status,
            "candidate_ownership": self.candidate_ownership,
            "candidate_ownership_confidence": self.candidate_ownership_confidence,
            "requires_confirmation": self.requires_confirmation,
            "repository_signal": self.repository_signal,
            "source": self.source,
            "source_evidence_ids": list(self.source_evidence_ids),
        }


@dataclass(frozen=True)
class RepositoryAchievementGenerationResult:
    profile_id: UUID
    extraction_id: UUID | None
    achievements: list[Any]
    warnings: list[str] = field(default_factory=list)


class RepositoryAchievementService:
    """Synthesize review-ready project drafts from repository architecture evidence.

    Core invariant: no candidate/domain-specific narrative synthesis here.
    """

    engineering_invariant = CORE_SERVICE_INVARIANT

    def __init__(
        self,
        *,
        evidence_repository: EvidenceSnippetRepository | None = None,
        achievement_repository: CandidateAchievementRepository | None = None,
        file_extraction_repository: Any | None = None,
    ) -> None:
        self.evidence_repository = evidence_repository or EvidenceSnippetRepository()
        self.achievement_repository = (
            achievement_repository or CandidateAchievementRepository()
        )

    async def generate_repository_achievement_drafts(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        profile_id: UUID,
    ) -> RepositoryAchievementGenerationResult:
        snippets = await self.evidence_repository.list_by_user_id(
            session,
            user_id=user_id,
            source_types=["github_public"],
        )
        evidence_items = [
            {
                "id": str(snippet.id),
                "title": snippet.title,
                "snippet_text": snippet.snippet_text,
                "source_type": snippet.source_type,
                "skills": list(snippet.skills_json or []),
                "evidence_strength": snippet.evidence_strength,
                "fact_status": snippet.fact_status,
                "star_summary": dict(snippet.star_summary_json or {}),
            }
            for snippet in snippets
        ]
        drafts = self.synthesize_project_drafts(evidence_items)

        warnings: list[str] = []
        if not evidence_items:
            warnings.append("no github repository evidence found")
        elif not drafts:
            warnings.append("no architecture evidence found for repository achievement drafts")

        created_items = await self.achievement_repository.append_for_profile(
            session,
            profile_id=profile_id,
            achievements=[
                self._draft_to_achievement_payload(draft)
                for draft in drafts
            ],
        )
        if drafts and not created_items:
            warnings.append("repository achievement drafts already exist")

        achievements = await self.achievement_repository.list_for_profile(
            session,
            profile_id=profile_id,
        )

        return RepositoryAchievementGenerationResult(
            profile_id=profile_id,
            extraction_id=None,
            achievements=achievements,
            warnings=warnings,
        )

    def synthesize_project_drafts(
        self,
        architecture_evidence: Sequence[Mapping[str, Any]],
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        grouped = self._group_architecture_evidence(architecture_evidence)
        drafts = [
            self._build_project_draft(project_key=project_key, items=items)
            for project_key, items in grouped.items()
            if items
        ]
        drafts.sort(
            key=lambda item: (
                self._evidence_count(item),
                len(item.source_evidence_ids),
            ),
            reverse=True,
        )
        return [draft.as_dict() for draft in drafts[:limit]]

    def _group_architecture_evidence(
        self,
        evidence_items: Sequence[Mapping[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for raw_item in evidence_items:
            item = dict(raw_item)
            if not self._is_architecture_evidence(item):
                continue
            project_key = self._project_key(item)
            grouped.setdefault(project_key, []).append(item)
        return grouped

    def _is_architecture_evidence(self, item: Mapping[str, Any]) -> bool:
        star_summary = dict(item.get("star_summary") or {})
        return (
            str(item.get("type") or "").strip().lower() == "architecture_evidence"
            or str(item.get("category") or "").strip().lower() == "architecture_evidence"
            or str(star_summary.get("type") or "").strip().lower() == "architecture_evidence"
            or str(star_summary.get("category") or "").strip().lower()
            == "architecture_evidence"
        )

    def _project_key(self, item: Mapping[str, Any]) -> str:
        star_summary = dict(item.get("star_summary") or {})
        project = str(star_summary.get("project") or "").strip()
        if project:
            return project

        source_url = str(star_summary.get("source_url") or "").strip()
        if source_url:
            return source_url.rstrip("/").rsplit("/", 1)[-1]

        title = str(item.get("title") or "").strip()
        if ":" in title:
            return title.split(":", 1)[0].strip()

        return "repository_project"

    def _build_project_draft(
        self,
        *,
        project_key: str,
        items: list[dict[str, Any]],
    ) -> RepositoryAchievementDraft:
        skills = self._aggregate_skills(items)
        title = self._draft_title(skills=skills)
        summary = self._summary(project_key=project_key, items=items, skills=skills)
        evidence_ids = [
            str(item.get("id") or item.get("evidence_id") or "").strip()
            for item in items
            if str(item.get("id") or item.get("evidence_id") or "").strip()
        ]
        return RepositoryAchievementDraft(
            title=title,
            skills=skills,
            summary=summary,
            situation=None,
            task="Review candidate ownership before using repository signals in documents.",
            action=summary,
            result=None,
            fact_status="needs_confirmation",
            candidate_ownership="unknown",
            candidate_ownership_confidence="low",
            requires_confirmation=True,
            repository_signal=True,
            source="github_repository_analysis",
            source_evidence_ids=self._dedupe(evidence_ids),
        )

    def _aggregate_skills(self, items: Sequence[Mapping[str, Any]]) -> list[str]:
        skills: list[str] = []
        for item in items:
            skills.extend(
                str(skill).strip()
                for skill in (item.get("skills") or [])
                if str(skill).strip()
            )

        skills = self._dedupe(skills)
        return sorted(
            skills,
            key=lambda value: value.strip().lower(),
        )

    def _draft_title(
        self,
        *,
        skills: list[str],
    ) -> str:
        scope = self._implementation_scope(skills)
        return f"Repository evidence: {scope} implementation signals"

    def _summary(
        self,
        *,
        project_key: str,
        items: Sequence[Mapping[str, Any]],
        skills: list[str],
    ) -> str:
        skill_text = ", ".join(skills[:6])
        scope = self._implementation_scope(skills)

        parts = [
            f"Repository evidence indicates {scope} implementation signals.",
            f"Signals found: {skill_text}." if skill_text else "",
            "Candidate ownership is unknown and confidence is low.",
            "Requires candidate confirmation before use in resume.",
        ]
        return " ".join(part for part in parts if part).strip()

    def _implementation_scope(self, skills: Sequence[str]) -> str:
        normalized = {skill.strip().lower() for skill in skills}
        backend_markers = {
            "api",
            "async api",
            "backend",
            "backend architecture",
            "database",
            "fastapi",
            "postgresql",
            "sqlalchemy",
            "persistence layer",
            "docker",
            "infrastructure",
        }
        if normalized.intersection(backend_markers):
            return "backend-related"
        if normalized:
            return "technical"
        return "repository"

    def _skill_summary(self, skills: Sequence[str], *, limit: int) -> str:
        return ", ".join(
            skill
            for skill in self._dedupe(
                [str(skill).strip() for skill in skills if str(skill).strip()]
            )[:limit]
        )

    def _draft_to_achievement_payload(self, draft: Mapping[str, Any]) -> dict[str, Any]:
        skills = [
            str(skill).strip()
            for skill in (draft.get("skills") or [])
            if str(skill).strip()
        ]
        source_ids = [
            str(item).strip()
            for item in (draft.get("source_evidence_ids") or [])
            if str(item).strip()
        ]
        evidence_note_parts = [
            "Repository evidence indicates implementation signals; candidate ownership is unknown.",
            "Candidate ownership confidence: low.",
            "Requires candidate confirmation before use in resume.",
            "Skills: " + ", ".join(skills[:8]) if skills else "",
            "Evidence ids: " + ", ".join(source_ids[:8]) if source_ids else "",
        ]
        return {
            "title": str(draft.get("title") or "").strip(),
            "situation": str(draft.get("situation") or "").strip() or None,
            "task": str(draft.get("task") or "").strip()
            or "Review candidate ownership before using repository signals in documents.",
            "action": str(draft.get("action") or draft.get("summary") or "").strip() or None,
            "result": str(draft.get("result") or "").strip() or None,
            "metric_text": None,
            "evidence_note": " ".join(part for part in evidence_note_parts if part),
            "fact_status": str(draft.get("fact_status") or "needs_confirmation"),
            "experience_id": None,
        }

    def _evidence_count(self, draft: RepositoryAchievementDraft) -> int:
        return len(draft.source_evidence_ids)

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = re.sub(r"\s+", " ", str(value).strip())
            normalized = cleaned.lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(cleaned)
        return result
