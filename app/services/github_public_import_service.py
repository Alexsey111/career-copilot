# app\services\github_public_import_service.py

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.evidence import build_evidence_fingerprint, extract_skill_tags
from app.domain.text_normalization import strip_emoji
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.schemas.profile_intake import GitHubPublicProfileImportRequest
from app.services.github_repository_evidence_service import GitHubRepositoryEvidenceService
from app.services.profile_intake_service import ProfileIntakeResult, ProfileIntakeService


GITHUB_SIGNAL_KEYWORDS = [
    "ai",
    "automation",
    "workflow",
    "fastapi",
    "langchain",
    "openai",
    "telegram",
    "bot",
    "docker",
    "ml",
    "machine learning",
    "computer vision",
    "cv",
]

STACK_SIGNAL_PATTERNS = {
    "FastAPI": ["fastapi", "APIRouter"],
    "SQLAlchemy": ["sqlalchemy"],
    "Alembic": ["alembic"],
    "PostgreSQL": ["postgres", "postgresql", "psycopg", "asyncpg"],
    "Redis": ["redis"],
    "Docker": ["docker-compose", "Dockerfile", "FROM python"],
    "Pytest": ["pytest", "tests/"],
    "OpenAI": ["openai"],
    "Telegram Bot": ["aiogram", "python-telegram-bot", "telegram"],
}


@dataclass(frozen=True)
class GitHubProjectDraft:
    name: str
    description: str | None
    url: str | None
    languages: list[str]
    topics: list[str]
    readme_snippet: str | None
    dependency_files: dict[str, str]
    repo_files: list[str]
    source_files: dict[str, str]


class GitHubPublicImportError(RuntimeError):
    """Raised when GitHub public data cannot be fetched reliably."""


class GitHubPublicImportService:
    def __init__(
        self,
        *,
        profile_intake_service: ProfileIntakeService | None = None,
        evidence_repository: EvidenceSnippetRepository | None = None,
        repository_evidence_service: GitHubRepositoryEvidenceService | None = None,
        http_timeout_seconds: float = 10.0,
    ) -> None:
        self.profile_intake_service = profile_intake_service or ProfileIntakeService()
        self.evidence_repository = evidence_repository or EvidenceSnippetRepository()
        self.repository_evidence_service = (
            repository_evidence_service or GitHubRepositoryEvidenceService()
        )
        self.http_timeout_seconds = http_timeout_seconds

    async def import_public_profile(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        payload: GitHubPublicProfileImportRequest,
    ) -> ProfileIntakeResult:
        username = self._extract_username(payload.profile_url)
        projects = await self._fetch_projects(
            username=username,
            max_repositories=payload.max_repositories,
            include_readme=payload.include_readme,
        )
        raw_payload = {
            "profile_url": payload.profile_url,
            "username": username,
            "target_role": payload.target_role,
            "repositories": [project.__dict__ for project in projects],
        }
        raw_text = self._projects_to_text(
            username=username,
            profile_url=payload.profile_url,
            target_role=payload.target_role,
            projects=projects,
        )
        # Эмодзи вырезаем на границе загрузки (см. text_normalization.strip_emoji),
        # чтобы детерминированный downstream не получал эмодзи из описаний репо.
        raw_text = strip_emoji(raw_text)

        profile = await self.profile_intake_service._get_or_create_profile(
            session,
            user_id=user_id,
        )
        technologies = self.profile_intake_service._dedupe(
            [language for project in projects for language in project.languages]
        )
        self.profile_intake_service._apply_personal(
            profile,
            name=None,
            location=None,
            target_role=payload.target_role,
            technologies=technologies,
            ai_tools=[],
            automation_tools=[],
            market=payload.market,
        )
        source_file, extraction = await self.profile_intake_service._create_raw_source(
            session,
            user_id=user_id,
            source="github_public",
            raw_text=raw_text,
            raw_payload=raw_payload,
        )
        snippets = await self._upsert_github_public_evidence(
            session,
            user_id=user_id,
            projects=projects,
        )

        return ProfileIntakeResult(
            profile=profile,
            source_file_id=source_file.id,
            extraction_id=extraction.id,
            source="github_public",
            raw_text=raw_text,
            evidence_snippets=snippets,
            technologies=technologies,
            project_count=len(projects),
        )

    async def _fetch_projects(
        self,
        *,
        username: str,
        max_repositories: int,
        include_readme: bool,
    ) -> list[GitHubProjectDraft]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "career-copilot-mvp",
        }
        async with httpx.AsyncClient(timeout=self.http_timeout_seconds, headers=headers) as client:
            try:
                repos_response = await client.get(
                    f"https://api.github.com/users/{username}/repos",
                    params={
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": max_repositories,
                        "type": "owner",
                    },
                )
                repos_response.raise_for_status()
                repos_payload = repos_response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 404:
                    raise GitHubPublicImportError(
                        f"GitHub profile '{username}' was not found."
                    ) from exc
                if status_code == 403:
                    raise GitHubPublicImportError(
                        "GitHub API rate limit or access policy blocked this import. Try again later."
                    ) from exc
                raise GitHubPublicImportError(
                    f"GitHub API returned HTTP {status_code} while loading repositories."
                ) from exc
            except httpx.RequestError as exc:
                raise GitHubPublicImportError(
                    "GitHub API is temporarily unavailable. Check backend network/DNS access and try again."
                ) from exc
            except ValueError as exc:
                raise GitHubPublicImportError(
                    "GitHub API returned an unexpected repositories payload."
                ) from exc

            if not isinstance(repos_payload, list):
                raise GitHubPublicImportError(
                    "GitHub API returned an unexpected repositories payload."
                )

            projects: list[GitHubProjectDraft] = []
            for repo in repos_payload[:max_repositories]:
                if repo.get("fork"):
                    continue
                languages = await self._fetch_languages(client, repo)
                readme = (
                    await self._fetch_readme_snippet(client, repo)
                    if include_readme
                    else None
                )
                dependency_files = await self._fetch_dependency_files(client, repo)
                repo_files = await self._fetch_repo_files(client, repo)
                source_files = await self._fetch_source_files(
                    client,
                    repo=repo,
                    repo_files=repo_files,
                )
                projects.append(
                    GitHubProjectDraft(
                        name=str(repo.get("name") or ""),
                        description=repo.get("description"),
                        url=repo.get("html_url"),
                        languages=languages,
                        topics=[str(item) for item in (repo.get("topics") or []) if str(item).strip()],
                        readme_snippet=readme,
                        dependency_files=dependency_files,
                        repo_files=repo_files,
                        source_files=source_files,
                    )
                )
            return projects

    async def _fetch_languages(self, client: httpx.AsyncClient, repo: dict[str, Any]) -> list[str]:
        languages_url = str(repo.get("languages_url") or "").strip()
        if not languages_url:
            return []
        try:
            response = await client.get(languages_url)
        except httpx.RequestError:
            return []
        if response.status_code >= 400:
            return []
        try:
            payload = response.json()
        except ValueError:
            return []
        if not isinstance(payload, dict):
            return []
        return [str(name) for name in payload if str(name).strip()]

    async def _fetch_readme_snippet(self, client: httpx.AsyncClient, repo: dict[str, Any]) -> str | None:
        full_name = str(repo.get("full_name") or "").strip()
        if not full_name:
            return None
        try:
            response = await client.get(f"https://api.github.com/repos/{full_name}/readme")
        except httpx.RequestError:
            return None
        if response.status_code >= 400:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        encoded = str(payload.get("content") or "")
        if not encoded:
            return None
        try:
            decoded = base64.b64decode(encoded, validate=False).decode("utf-8", errors="ignore")
        except Exception:
            return None
        return " ".join(decoded.split())[:700] or None

    async def _fetch_dependency_files(self, client: httpx.AsyncClient, repo: dict[str, Any]) -> dict[str, str]:
        full_name = str(repo.get("full_name") or "").strip()
        if not full_name:
            return {}

        candidates = [
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "docker-compose.yml",
            "docker-compose.yaml",
            "Dockerfile",
        ]

        result: dict[str, str] = {}
        for path in candidates:
            try:
                response = await client.get(f"https://api.github.com/repos/{full_name}/contents/{path}")
            except httpx.RequestError:
                continue

            if response.status_code >= 400:
                continue

            try:
                payload = response.json()
            except ValueError:
                continue

            encoded = str(payload.get("content") or "")
            if not encoded:
                continue

            try:
                decoded = base64.b64decode(encoded, validate=False).decode("utf-8", errors="ignore")
            except Exception:
                continue

            result[path] = decoded[:5000]

        return result

    async def _fetch_repo_files(self, client: httpx.AsyncClient, repo: dict[str, Any]) -> list[str]:
        full_name = str(repo.get("full_name") or "").strip()
        if not full_name:
            return []

        try:
            response = await client.get(
                f"https://api.github.com/repos/{full_name}/git/trees/HEAD",
                params={"recursive": "1"},
            )
        except httpx.RequestError:
            return []

        if response.status_code >= 400:
            return []

        try:
            payload = response.json()
        except ValueError:
            return []

        tree = payload.get("tree") or []
        if not isinstance(tree, list):
            return []

        paths = [
            str(item.get("path") or "")
            for item in tree
            if str(item.get("path") or "").strip()
        ]
        return paths[:300]

    async def _fetch_source_files(
        self,
        client: httpx.AsyncClient,
        *,
        repo: dict[str, Any],
        repo_files: list[str],
    ) -> dict[str, str]:
        full_name = str(repo.get("full_name") or "").strip()
        if not full_name:
            return {}

        candidates = self._source_file_candidates(repo_files)
        result: dict[str, str] = {}
        for path in candidates:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{full_name}/contents/{path}"
                )
            except httpx.RequestError:
                continue

            if response.status_code >= 400:
                continue

            try:
                payload = response.json()
            except ValueError:
                continue

            encoded = str(payload.get("content") or "")
            if not encoded:
                continue

            try:
                decoded = base64.b64decode(encoded, validate=False).decode("utf-8", errors="ignore")
            except Exception:
                continue

            result[path] = decoded[:8000]

        return result

    def _source_file_candidates(self, repo_files: list[str]) -> list[str]:
        python_files = [
            path
            for path in repo_files
            if path.endswith(".py")
            and not path.endswith("__init__.py")
            and not any(part in path.lower() for part in (".venv/", "site-packages/"))
        ]

        def priority(path: str) -> tuple[int, int, str]:
            lowered = path.lower()
            score = 10
            if "main.py" in lowered or "app.py" in lowered:
                score = 0
            elif "/api/" in lowered or "/routes/" in lowered or "/routers/" in lowered:
                score = 1
            elif "models" in lowered or "database" in lowered or "repository" in lowered:
                score = 2
            elif lowered.startswith("alembic/") or "/migrations/" in lowered:
                score = 3
            elif lowered.startswith("tests/") or "/tests/" in lowered:
                score = 4
            return (score, len(path), path)

        return sorted(python_files, key=priority)[:25]

    async def _upsert_github_public_evidence(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        projects: list[GitHubProjectDraft],
    ):
        snippets = []
        for project in projects:
            text = self._project_text(project)
            skills = self._project_skills(project)
            snippets.append(
                self._snippet(
                    user_id=user_id,
                    title=project.name,
                    text=text,
                    skills=skills,
                    category="project",
                    source_url=project.url,
                )
            )
            signal_skills = self._signal_skills(project)
            if signal_skills:
                snippets.append(
                    self._snippet(
                        user_id=user_id,
                        title=f"{project.name} signals",
                        text=", ".join(signal_skills),
                        skills=signal_skills,
                        category="competency_signal",
                        source_url=project.url,
                    )
                )
            for evidence in self.repository_evidence_service.analyze_repository(
                name=project.name,
                description=project.description,
                url=project.url,
                languages=project.languages,
                topics=project.topics,
                readme_snippet=project.readme_snippet,
                dependency_files=project.dependency_files,
                repo_files=project.repo_files,
                source_files=project.source_files,
            ):
                snippets.append(
                    self._repository_evidence_snippet(
                        user_id=user_id,
                        project=project,
                        evidence=evidence,
                    )
                )
        return await self.evidence_repository.upsert_many(
            session,
            user_id=user_id,
            snippets=snippets,
        )

    def _snippet(
        self,
        *,
        user_id: UUID,
        title: str,
        text: str,
        skills: list[str],
        category: str,
        source_url: str | None,
    ) -> dict[str, Any]:
        extracted_skills = self.profile_intake_service._dedupe([*skills, *extract_skill_tags(title, text)])
        detected_stack = [skill for skill in extracted_skills if skill in STACK_SIGNAL_PATTERNS]
        fact_status = "needs_confirmation"
        source_type = "github_public"
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
            "evidence_strength": "strong" if detected_stack else "medium" if extracted_skills else "weak",
            "fact_status": fact_status,
            "star_summary": {
                "category": category,
                "source": "github_public_import_v1",
                "source_url": source_url,
                "summary": text,
            },
        }

    def _repository_evidence_snippet(
        self,
        *,
        user_id: UUID,
        project: GitHubProjectDraft,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        source_type = "github_public"
        fact_status = str(evidence.get("fact_status") or "needs_confirmation").strip()
        title = str(evidence.get("title") or "").strip() or "Repository evidence"
        snippet_text = str(evidence.get("snippet_text") or "").strip() or title
        skills = self.profile_intake_service._dedupe(
            [
                str(skill)
                for skill in (evidence.get("skills") or [])
                if str(skill).strip()
            ]
        )
        return {
            "fingerprint": build_evidence_fingerprint(
                user_id=str(user_id),
                title=f"{project.name}: {title}",
                snippet_text=snippet_text,
                source_type=source_type,
                skills=skills,
                fact_status=fact_status,
            ),
            "title": title,
            "snippet_text": snippet_text,
            "source_type": source_type,
            "skills": skills,
            "evidence_strength": str(evidence.get("evidence_strength") or "medium").strip().lower(),
            "fact_status": fact_status,
            "star_summary": {
                "type": str(evidence.get("type") or "architecture_evidence"),
                "category": str(evidence.get("type") or "architecture_evidence"),
                "source": str(evidence.get("source") or "github_repository_analysis"),
                "source_url": project.url,
                "project": project.name,
                "signals": list(evidence.get("signals") or []),
                "summary": snippet_text,
            },
        }

    def _project_text(self, project: GitHubProjectDraft) -> str:
        detected_stack = self._detected_stack_from_repo_files(project)
        return " ".join(
            part
            for part in [
                project.description or "",
                "Languages: " + ", ".join(project.languages) if project.languages else "",
                "Topics: " + ", ".join(project.topics) if project.topics else "",
                "Detected stack: " + ", ".join(detected_stack)
                if detected_stack
                else "",
                "Repository files: " + ", ".join(project.repo_files[:30])
                if project.repo_files
                else "",
                "Source files analyzed: " + ", ".join(project.source_files.keys())
                if project.source_files
                else "",
                project.readme_snippet or "",
                project.url or "",
            ]
            if part
        ) or project.name

    def _project_skills(self, project: GitHubProjectDraft) -> list[str]:
        return self.profile_intake_service._dedupe(
            [
                *project.languages,
                *project.topics,
                *self._detected_stack_from_repo_files(project),
            ]
        )

    def _detected_stack_from_repo_files(self, project: GitHubProjectDraft) -> list[str]:
        corpus_parts = [
            project.readme_snippet or "",
            "\n".join(project.repo_files),
            "\n".join(project.dependency_files.values()),
            " ".join(project.topics),
            " ".join(project.languages),
        ]
        corpus = "\n".join(corpus_parts).casefold()

        detected: list[str] = []
        for skill, patterns in STACK_SIGNAL_PATTERNS.items():
            if any(pattern.casefold() in corpus for pattern in patterns):
                detected.append(skill)

        return self.profile_intake_service._dedupe(detected)

    def _signal_skills(self, project: GitHubProjectDraft) -> list[str]:
        text = self._project_text(project).lower()
        signals = [
            keyword
            for keyword in GITHUB_SIGNAL_KEYWORDS
            if keyword in text
        ]
        return self.profile_intake_service._dedupe([*signals, *extract_skill_tags(text)])

    def _projects_to_text(
        self,
        *,
        username: str,
        profile_url: str,
        target_role: str | None,
        projects: list[GitHubProjectDraft],
    ) -> str:
        lines = [
            "GITHUB PUBLIC PROFILE IMPORT",
            f"Username: {username}",
            f"Profile URL: {profile_url}",
            f"Target role: {target_role or ''}",
        ]
        for project in projects:
            lines.extend(
                [
                    "",
                    f"Repository: {project.name}",
                    f"Description: {project.description or ''}",
                    "Languages: " + ", ".join(project.languages),
                    "Topics: " + ", ".join(project.topics),
                    "Detected stack: " + ", ".join(self._detected_stack_from_repo_files(project)),
                    "Repository files: " + ", ".join(project.repo_files[:30]),
                    "Source files analyzed: " + ", ".join(project.source_files.keys()),
                    f"README: {project.readme_snippet or ''}",
                    f"URL: {project.url or ''}",
                ]
            )
        return "\n".join(lines).strip()

    def _extract_username(self, profile_url: str) -> str:
        value = profile_url.strip()
        if re.fullmatch(r"[A-Za-z0-9-]+", value):
            return value
        parsed = urlparse(value)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("profile_url must point to github.com")
        username = parsed.path.strip("/").split("/", 1)[0]
        if not re.fullmatch(r"[A-Za-z0-9-]+", username or ""):
            raise ValueError("profile_url must include a GitHub username")
        return username
