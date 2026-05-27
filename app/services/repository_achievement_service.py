# app\services\repository_achievement_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.file_extraction_repository import FileExtractionRepository


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
    """Synthesize review-ready project drafts from repository architecture evidence."""

    def __init__(
        self,
        *,
        evidence_repository: EvidenceSnippetRepository | None = None,
        achievement_repository: CandidateAchievementRepository | None = None,
        file_extraction_repository: FileExtractionRepository | None = None,
    ) -> None:
        self.evidence_repository = evidence_repository or EvidenceSnippetRepository()
        self.achievement_repository = (
            achievement_repository or CandidateAchievementRepository()
        )
        self.file_extraction_repository = (
            file_extraction_repository or FileExtractionRepository()
        )

    async def generate_repository_achievement_drafts(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        profile_id: UUID,
    ) -> RepositoryAchievementGenerationResult:
        extraction = await self.file_extraction_repository.get_latest_for_active_source_file_kind(
            session,
            user_id,
            file_kind="resume",
        )
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
            extraction_id=extraction.id if extraction is not None else None,
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
                len(item.skills),
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
        title = self._draft_title(skills=skills, items=items)
        summary = self._summary(project_key=project_key, items=items, skills=skills)
        star = self._star_narrative(project_key=project_key, items=items, skills=skills)
        evidence_ids = [
            str(item.get("id") or item.get("evidence_id") or "").strip()
            for item in items
            if str(item.get("id") or item.get("evidence_id") or "").strip()
        ]
        return RepositoryAchievementDraft(
            title=title,
            skills=skills,
            summary=summary,
            situation=star["situation"],
            task=star["task"],
            action=star["action"],
            result=star["result"],
            fact_status="needs_confirmation",
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
        priority = {
            "fastapi": 0,
            "openai": 1,
            "ai workflow": 2,
            "workflow orchestration": 3,
            "backend architecture": 4,
            "async api": 5,
            "postgresql": 6,
            "sqlalchemy": 7,
            "persistence layer": 8,
            "docker": 9,
            "infrastructure": 10,
            "pytest": 11,
            "testing": 12,
        }
        return sorted(
            skills,
            key=lambda value: (
                priority.get(value.strip().lower(), 100),
                value.strip().lower(),
            ),
        )

    def _draft_title(
        self,
        *,
        skills: list[str],
        items: Sequence[Mapping[str, Any]],
    ) -> str:
        skill_set = {skill.strip().lower() for skill in skills}
        title_text = " ".join(str(item.get("title") or "") for item in items).lower()

        if (
            "ai workflow" in skill_set
            or "workflow orchestration" in skill_set
            or "implemented ai workflow orchestration" in title_text
        ):
            return "Разработка AI workflow orchestration системы"

        if "fastapi" in skill_set or "backend architecture" in skill_set:
            return "Разработка FastAPI backend сервиса"

        if (
            "postgresql" in skill_set
            or "sqlalchemy" in skill_set
            or "persistence layer" in skill_set
        ):
            return "Проектирование PostgreSQL persistence layer"

        if "docker" in skill_set or "infrastructure" in skill_set:
            return "Настройка Docker-based инфраструктуры"

        return "Разработка backend repository architecture"

    def _summary(
        self,
        *,
        project_key: str,
        items: Sequence[Mapping[str, Any]],
        skills: list[str],
    ) -> str:
        capability_titles = self._dedupe(
            [
                str(item.get("title") or "").strip()
                for item in items
                if str(item.get("title") or "").strip()
            ]
        )
        capability_text = "; ".join(capability_titles[:4])
        skill_text = ", ".join(skills[:6])
        project_phrase = (
            f"На основе GitHub repository evidence по проекту {project_key}"
            if project_key != "repository_project"
            else "На основе GitHub repository evidence"
        )

        parts = [
            project_phrase,
            f"синтезирован проектный черновик: {capability_text}"
            if capability_text
            else "синтезирован проектный черновик",
            f"Ключевые навыки: {skill_text}" if skill_text else "",
            "Требует подтверждения кандидатом перед использованием в документах.",
        ]
        return " ".join(part for part in parts if part).strip()

    def _star_narrative(
        self,
        *,
        project_key: str,
        items: Sequence[Mapping[str, Any]],
        skills: list[str],
    ) -> dict[str, str]:
        skill_set = {skill.strip().lower() for skill in skills}
        title_text = " ".join(str(item.get("title") or "") for item in items).lower()
        snippet_text = " ".join(str(item.get("snippet_text") or "") for item in items).lower()
        corpus = " ".join([title_text, snippet_text, " ".join(skill_set)])
        project_name = self._display_project_name(project_key)

        has_ai_workflow = any(
            marker in skill_set
            for marker in {"ai workflow", "workflow orchestration", "openai", "llm"}
        ) or any(marker in corpus for marker in ("workflow", "orchestrat", "openai", "llm"))
        has_fastapi = any(
            marker in skill_set
            for marker in {"fastapi", "backend architecture", "async api"}
        )
        has_persistence = any(
            marker in skill_set
            for marker in {"postgresql", "sqlalchemy", "persistence layer", "async database"}
        )
        has_infra = any(
            marker in skill_set
            for marker in {"docker", "infrastructure", "redis", "celery"}
        )
        has_testing = any(
            marker in skill_set
            for marker in {"pytest", "testing", "test automation"}
        )

        situation = (
            f"Нужно было собрать инженерную основу проекта {project_name}, "
            "где backend, AI workflow и review-процессы должны работать как единый продуктовый pipeline."
            if has_ai_workflow
            else f"Нужно было оформить repository evidence проекта {project_name} в проверяемый инженерный опыт."
        )

        task_parts: list[str] = []
        if has_fastapi:
            task_parts.append("спроектировать FastAPI backend")
        if has_persistence:
            task_parts.append("подготовить persistence layer")
        if has_ai_workflow:
            task_parts.append("связать AI orchestration flow")
        if has_infra:
            task_parts.append("настроить локальную инфраструктуру")
        if has_testing:
            task_parts.append("закрыть поведение автотестами")

        task = (
            "Задача: "
            + ", ".join(task_parts)
            + "."
            if task_parts
            else "Задача: описать архитектурный вклад на основе GitHub evidence."
        )

        action_parts: list[str] = []
        if has_fastapi and has_ai_workflow:
            action_parts.append(
                f"Спроектировал FastAPI backend для {project_name}, включающий "
                "pipeline анализа вакансий, генерацию tailored resume и workflow review"
            )
        elif has_fastapi:
            action_parts.append(
                f"Спроектировал FastAPI backend для {project_name} с async API и routing architecture"
            )
        if has_persistence:
            action_parts.append(
                "описал PostgreSQL/SQLAlchemy persistence layer для хранения документов, evidence и workflow-состояний"
            )
        if has_infra:
            action_parts.append(
                "выделил Docker-based инфраструктуру для локального запуска и интеграций"
            )
        if has_testing:
            action_parts.append(
                "зафиксировал automated testing signals как подтверждение проверяемости решения"
            )

        action = ". ".join(action_parts) + "." if action_parts else self._summary(
            project_key=project_key,
            items=items,
            skills=skills,
        )

        result_parts = [
            "Получился review-ready проектный нарратив, который связывает repository evidence с инженерными capability."
        ]
        if has_ai_workflow and has_fastapi:
            result_parts.append(
                "Его можно использовать в резюме как evidence-backed backend/AI workflow experience."
            )
        result = " ".join(result_parts)

        return {
            "situation": situation,
            "task": task,
            "action": action,
            "result": result,
        }

    def _display_project_name(self, project_key: str) -> str:
        cleaned = re.sub(r"[-_]+", " ", project_key).strip()
        if cleaned.lower() == "career copilot":
            return "AI Career Copilot"
        return cleaned.title() if cleaned else "repository project"

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
            "Synthesized from GitHub repository architecture evidence; requires user confirmation.",
            "Skills: " + ", ".join(skills[:8]) if skills else "",
            "Evidence ids: " + ", ".join(source_ids[:8]) if source_ids else "",
        ]
        return {
            "title": str(draft.get("title") or "").strip(),
            "situation": str(draft.get("situation") or "").strip() or None,
            "task": str(draft.get("task") or "").strip()
            or "Сформировать проектный опыт на основе GitHub repository evidence.",
            "action": str(draft.get("action") or draft.get("summary") or "").strip() or None,
            "result": str(draft.get("result") or "").strip() or None,
            "metric_text": None,
            "evidence_note": " ".join(part for part in evidence_note_parts if part),
            "fact_status": str(draft.get("fact_status") or "needs_confirmation"),
            "experience_id": None,
        }

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
