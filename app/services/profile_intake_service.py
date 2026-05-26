# app\services\profile_intake_service.py

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.evidence import build_evidence_fingerprint, extract_skill_tags
from app.models import CandidateAchievement, CandidateExperience, CandidateProfile
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository
from app.schemas.profile_intake import (
    GitHubProfileIntakeRequest,
    ManualProfileIntakeRequest,
)


@dataclass
class ProfileIntakeResult:
    profile: CandidateProfile
    source_file_id: UUID
    extraction_id: UUID
    source: str
    raw_text: str
    experiences: list[CandidateExperience] = field(default_factory=list)
    achievements: list[CandidateAchievement] = field(default_factory=list)
    evidence_snippets: list[Any] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    ai_tools: list[str] = field(default_factory=list)
    automation_tools: list[str] = field(default_factory=list)
    project_count: int = 0


class ProfileIntakeService:
    def __init__(
        self,
        *,
        profile_repository: CandidateProfileRepository | None = None,
        source_file_repository: SourceFileRepository | None = None,
        file_extraction_repository: FileExtractionRepository | None = None,
        evidence_repository: EvidenceSnippetRepository | None = None,
    ) -> None:
        self.profile_repository = profile_repository or CandidateProfileRepository()
        self.source_file_repository = source_file_repository or SourceFileRepository()
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.evidence_repository = evidence_repository or EvidenceSnippetRepository()

    async def ingest_manual_profile(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        payload: ManualProfileIntakeRequest,
    ) -> ProfileIntakeResult:
        raw_text = self._manual_payload_to_text(payload)
        profile = await self._get_or_create_profile(session, user_id=user_id)

        technologies = self._dedupe(payload.skills.technologies)
        ai_tools = self._dedupe(payload.skills.ai_tools)
        automation_tools = self._dedupe(payload.skills.automation_tools)

        self._apply_personal(
            profile,
            name=payload.personal.name,
            location=payload.personal.location,
            target_role=payload.personal.target_role,
            technologies=technologies,
            ai_tools=ai_tools,
            automation_tools=automation_tools,
        )
        experiences, achievements = await self._replace_profile_entries(
            session,
            profile=profile,
            experiences=[
                {
                    "company": item.company_or_project,
                    "role": item.role or payload.personal.target_role or "Project contributor",
                    "description_raw": self._experience_description(
                        what=item.what_did_you_do,
                        technologies=item.technologies,
                        results=item.results,
                    ),
                    "achievement": {
                        "title": item.company_or_project,
                        "action": item.what_did_you_do,
                        "result": item.results,
                        "metric_text": item.results,
                        "skills": item.technologies,
                    },
                }
                for item in payload.experience
            ],
            projects=[
                {
                    "title": item.title,
                    "description": item.description,
                    "stack": item.stack,
                    "results": item.results,
                }
                for item in payload.projects
            ],
        )
        source_file, extraction = await self._create_raw_source(
            session,
            user_id=user_id,
            source="manual",
            raw_text=raw_text,
            raw_payload=payload.model_dump(mode="json"),
        )
        snippets = await self._upsert_evidence_bank(
            session,
            user_id=user_id,
            source="manual",
            technologies=technologies,
            ai_tools=ai_tools,
            automation_tools=automation_tools,
            experiences=payload.experience,
            projects=payload.projects,
        )

        return ProfileIntakeResult(
            profile=profile,
            source_file_id=source_file.id,
            extraction_id=extraction.id,
            source="manual",
            raw_text=raw_text,
            experiences=experiences,
            achievements=achievements,
            evidence_snippets=snippets,
            technologies=technologies,
            ai_tools=ai_tools,
            automation_tools=automation_tools,
            project_count=len(payload.projects),
        )

    async def ingest_github_profile(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        payload: GitHubProfileIntakeRequest,
    ) -> ProfileIntakeResult:
        raw_text = self._github_payload_to_text(payload)
        profile = await self._get_or_create_profile(session, user_id=user_id)
        technologies = self._dedupe(
            [skill for repo in payload.repositories for skill in repo.stack]
        )
        self._apply_personal(
            profile,
            name=None,
            location=None,
            target_role=payload.target_role,
            technologies=technologies,
            ai_tools=[],
            automation_tools=[],
        )
        source_file, extraction = await self._create_raw_source(
            session,
            user_id=user_id,
            source="github",
            raw_text=raw_text,
            raw_payload=payload.model_dump(mode="json"),
        )
        snippets = await self._upsert_github_evidence(
            session,
            user_id=user_id,
            payload=payload,
        )

        return ProfileIntakeResult(
            profile=profile,
            source_file_id=source_file.id,
            extraction_id=extraction.id,
            source="github",
            raw_text=raw_text,
            evidence_snippets=snippets,
            technologies=technologies,
            project_count=len(payload.repositories),
        )

    async def _get_or_create_profile(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> CandidateProfile:
        profile = await self.profile_repository.get_with_related_by_user_id(session, user_id)
        if profile is None:
            profile = await self.profile_repository.create_empty(session, user_id=user_id)
            profile = await self.profile_repository.get_with_related_by_user_id(session, user_id) or profile
        return profile

    def _apply_personal(
        self,
        profile: CandidateProfile,
        *,
        name: str | None,
        location: str | None,
        target_role: str | None,
        technologies: list[str],
        ai_tools: list[str],
        automation_tools: list[str],
    ) -> None:
        if name:
            profile.full_name = name.strip()
        if location:
            profile.location = location.strip()
        if target_role:
            profile.target_roles_json = self._dedupe([target_role, *(profile.target_roles_json or [])])
            profile.headline = target_role.strip()

        summary_parts = []
        if technologies:
            summary_parts.append("Technologies: " + ", ".join(technologies))
        if ai_tools:
            summary_parts.append("AI tools: " + ", ".join(ai_tools))
        if automation_tools:
            summary_parts.append("Automation tools: " + ", ".join(automation_tools))
        if summary_parts:
            profile.summary = " | ".join(summary_parts)

    async def _replace_profile_entries(
        self,
        session: AsyncSession,
        *,
        profile: CandidateProfile,
        experiences: list[dict[str, Any]],
        projects: list[dict[str, Any]],
    ) -> tuple[list[CandidateExperience], list[CandidateAchievement]]:
        profile.experiences.clear()
        profile.achievements.clear()
        await session.flush()

        created_experiences: list[CandidateExperience] = []
        created_achievements: list[CandidateAchievement] = []
        order_index = 0

        for item in experiences:
            experience = CandidateExperience(
                profile_id=profile.id,
                company=item["company"],
                role=item["role"],
                description_raw=item["description_raw"],
                order_index=order_index,
            )
            session.add(experience)
            await session.flush()
            created_experiences.append(experience)

            achievement_data = item["achievement"]
            achievement = CandidateAchievement(
                profile_id=profile.id,
                experience_id=experience.id,
                title=achievement_data["title"],
                action=achievement_data.get("action"),
                result=achievement_data.get("result"),
                metric_text=achievement_data.get("metric_text"),
                evidence_note="User-provided guided intake experience",
                fact_status="needs_confirmation",
                order_index=order_index,
            )
            session.add(achievement)
            created_achievements.append(achievement)
            order_index += 1

        for project in projects:
            achievement = CandidateAchievement(
                profile_id=profile.id,
                title=project["title"],
                task=project.get("description"),
                action="Stack: " + ", ".join(project.get("stack") or []),
                result=project.get("results"),
                metric_text=project.get("results"),
                evidence_note="User-provided guided intake project",
                fact_status="needs_confirmation",
                order_index=order_index,
            )
            session.add(achievement)
            created_achievements.append(achievement)
            order_index += 1

        await session.flush()
        return created_experiences, created_achievements

    async def _create_raw_source(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source: str,
        raw_text: str,
        raw_payload: dict[str, Any],
    ):
        source_file = await self.source_file_repository.create(
            session,
            user_id=user_id,
            file_kind=f"{source}_profile",
            storage_key=f"{user_id}/{source}_profile/intake-{uuid.uuid4()}.json",
            original_name=f"{source}-profile-intake.json",
            mime_type="application/json",
            size_bytes=len(json.dumps(raw_payload, ensure_ascii=True).encode("utf-8")),
        )
        extraction = await self.file_extraction_repository.create(
            session,
            source_file_id=source_file.id,
            status="completed",
            parser_name=f"{source}_profile_intake",
            parser_version="v1",
            extracted_text=raw_text,
            extracted_metadata_json={
                "source": source,
                "raw_payload": raw_payload,
                "intake_version": "guided_intake_v1",
            },
        )
        return source_file, extraction

    async def _upsert_evidence_bank(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source: str,
        technologies: list[str],
        ai_tools: list[str],
        automation_tools: list[str],
        experiences: list[Any],
        projects: list[Any],
    ):
        snippets: list[dict[str, Any]] = []
        snippets.extend(
            self._tool_snippets(
                user_id=user_id,
                source=source,
                technologies=technologies,
                ai_tools=ai_tools,
                automation_tools=automation_tools,
            )
        )
        for item in experiences:
            title = item.company_or_project
            text = self._experience_description(
                what=item.what_did_you_do,
                technologies=item.technologies,
                results=item.results,
            )
            snippets.append(
                self._snippet(
                    user_id=user_id,
                    title=title,
                    text=text,
                    source_type="manual",
                    skills=item.technologies,
                    category="workflow_experience",
                    fact_status="user_provided",
                )
            )
        for item in projects:
            text = " ".join(
                part
                for part in [
                    item.description,
                    "Stack: " + ", ".join(item.stack) if item.stack else "",
                    item.results or "",
                ]
                if part
            )
            snippets.append(
                self._snippet(
                    user_id=user_id,
                    title=item.title,
                    text=text,
                    source_type="manual",
                    skills=item.stack,
                    category="project",
                    fact_status="user_provided",
                )
            )
        return await self.evidence_repository.upsert_many(
            session,
            user_id=user_id,
            snippets=snippets,
        )

    async def _upsert_github_evidence(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        payload: GitHubProfileIntakeRequest,
    ):
        snippets = []
        for repo in payload.repositories:
            text = " ".join(
                part
                for part in [
                    repo.description or "",
                    "Stack: " + ", ".join(repo.stack) if repo.stack else "",
                    "Highlights: " + "; ".join(repo.highlights) if repo.highlights else "",
                    repo.url or "",
                ]
                if part
            )
            snippets.append(
                self._snippet(
                    user_id=user_id,
                    title=repo.name,
                    text=text or repo.name,
                    source_type="manual",
                    skills=repo.stack,
                    category="project",
                    fact_status="user_provided",
                )
            )
        return await self.evidence_repository.upsert_many(
            session,
            user_id=user_id,
            snippets=snippets,
        )

    def _tool_snippets(
        self,
        *,
        user_id: UUID,
        source: str,
        technologies: list[str],
        ai_tools: list[str],
        automation_tools: list[str],
    ) -> list[dict[str, Any]]:
        groups = [
            ("Technologies", technologies, "technologies"),
            ("AI tools", ai_tools, "ai_project"),
            ("Automation tools", automation_tools, "automation"),
        ]
        snippets = []
        for title, skills, category in groups:
            if not skills:
                continue
            snippets.append(
                self._snippet(
                    user_id=user_id,
                    title=title,
                    text=", ".join(skills),
                    source_type="manual" if source == "manual" else "resume_structured",
                    skills=skills,
                    category=category,
                    fact_status="user_provided",
                )
            )
        return snippets

    def _snippet(
        self,
        *,
        user_id: UUID,
        title: str,
        text: str,
        source_type: str,
        skills: list[str],
        category: str,
        fact_status: str,
    ) -> dict[str, Any]:
        extracted_skills = self._dedupe([*skills, *extract_skill_tags(title, text)])
        return {
            "fingerprint": build_evidence_fingerprint(
                user_id=str(user_id),
                title=title,
                snippet_text=text,
                source_type=source_type,
                skills=extracted_skills,
                fact_status=fact_status,
            ),
            "title": title,
            "snippet_text": text,
            "source_type": source_type,
            "skills": extracted_skills,
            "evidence_strength": "medium" if extracted_skills else "weak",
            "fact_status": fact_status,
            "star_summary": {
                "category": category,
                "source": "guided_intake_v1",
                "summary": text,
            },
        }

    def _manual_payload_to_text(self, payload: ManualProfileIntakeRequest) -> str:
        lines = [
            "GUIDED PROFILE INTAKE",
            f"Name: {payload.personal.name or ''}",
            f"Location: {payload.personal.location or ''}",
            f"Target role: {payload.personal.target_role or ''}",
            "Technologies: " + ", ".join(payload.skills.technologies),
            "AI tools: " + ", ".join(payload.skills.ai_tools),
            "Automation tools: " + ", ".join(payload.skills.automation_tools),
        ]
        for item in payload.experience:
            lines.extend(
                [
                    "",
                    f"Experience: {item.company_or_project}",
                    f"Role: {item.role or ''}",
                    f"Did: {item.what_did_you_do}",
                    "Technologies: " + ", ".join(item.technologies),
                    f"Results: {item.results or ''}",
                ]
            )
        for item in payload.projects:
            lines.extend(
                [
                    "",
                    f"Project: {item.title}",
                    f"Description: {item.description}",
                    "Stack: " + ", ".join(item.stack),
                    f"Results: {item.results or ''}",
                ]
            )
        for item in payload.education:
            lines.extend(["", f"Education: {item.title}", item.institution or "", item.details or ""])
        return "\n".join(lines).strip()

    def _github_payload_to_text(self, payload: GitHubProfileIntakeRequest) -> str:
        lines = [
            "GITHUB PROFILE INTAKE",
            f"Username: {payload.username}",
            f"Profile URL: {payload.profile_url or ''}",
            f"Target role: {payload.target_role or ''}",
        ]
        for repo in payload.repositories:
            lines.extend(
                [
                    "",
                    f"Repository: {repo.name}",
                    f"Description: {repo.description or ''}",
                    "Stack: " + ", ".join(repo.stack),
                    "Highlights: " + "; ".join(repo.highlights),
                    f"URL: {repo.url or ''}",
                ]
            )
        return "\n".join(lines).strip()

    def _experience_description(
        self,
        *,
        what: str,
        technologies: list[str],
        results: str | None,
    ) -> str:
        parts = [what]
        if technologies:
            parts.append("Technologies: " + ", ".join(technologies))
        if results:
            parts.append("Results: " + results)
        return " ".join(parts)

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            key = cleaned.casefold()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result
