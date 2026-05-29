# app\services\github_repository_evidence_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RepositoryEvidence:
    type: str
    title: str
    skills: list[str]
    evidence_strength: str = "strong"
    fact_status: str = "needs_confirmation"
    source: str = "github_repository_analysis"
    snippet_text: str = ""
    signals: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "skills": list(self.skills),
            "evidence_strength": self.evidence_strength,
            "fact_status": self.fact_status,
            "source": self.source,
            "snippet_text": self.snippet_text,
            "signals": list(self.signals),
        }


class GitHubRepositoryEvidenceService:
    """Extract candidate-neutral technical signals from lightweight GitHub repo data."""

    def analyze_repository(
        self,
        *,
        name: str,
        description: str | None = None,
        url: str | None = None,
        languages: Sequence[str] | None = None,
        topics: Sequence[str] | None = None,
        readme_snippet: str | None = None,
        dependency_files: Mapping[str, str] | None = None,
        repo_files: Sequence[str] | None = None,
        source_files: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        snapshot = _RepositorySnapshot(
            name=name,
            description=description,
            url=url,
            languages=list(languages or []),
            topics=list(topics or []),
            readme_snippet=readme_snippet,
            dependency_files=dict(dependency_files or {}),
            repo_files=list(repo_files or []),
            source_files=dict(source_files or {}),
        )
        return [item.as_dict() for item in self._analyze(snapshot)]

    def _analyze(self, repo: "_RepositorySnapshot") -> list[RepositoryEvidence]:
        evidence: list[RepositoryEvidence] = []

        fastapi_signals = self._fastapi_architecture_signals(repo)
        if self._has_fastapi_architecture(fastapi_signals):
            evidence.append(
                RepositoryEvidence(
                    type="architecture_evidence",
                    title="Repository signal: FastAPI/API implementation",
                    skills=["FastAPI", "API", "Async API"],
                    evidence_strength=self._strength(fastapi_signals, strong_at=3),
                    snippet_text=self._sentence(
                        "Repository evidence indicates FastAPI/API implementation signals",
                        repo=repo,
                        signals=fastapi_signals,
                    ),
                    signals=fastapi_signals,
                )
            )

        persistence_signals = self._persistence_layer_signals(repo)
        if len(persistence_signals) >= 2:
            evidence.append(
                RepositoryEvidence(
                    type="architecture_evidence",
                    title="Repository signal: database persistence",
                    skills=[
                        "PostgreSQL",
                        "SQLAlchemy",
                        "Persistence Layer",
                        "Async Database",
                    ],
                    evidence_strength=self._strength(persistence_signals, strong_at=3),
                    snippet_text=self._sentence(
                        "Repository evidence indicates database persistence signals",
                        repo=repo,
                        signals=persistence_signals,
                    ),
                    signals=persistence_signals,
                )
            )

        infrastructure_signals = self._infrastructure_signals(repo)
        if len(infrastructure_signals) >= 2:
            evidence.append(
                RepositoryEvidence(
                    type="architecture_evidence",
                    title="Repository signal: containerized infrastructure",
                    skills=["Docker", "Infrastructure", *self._infra_skill_addons(infrastructure_signals)],
                    evidence_strength=self._strength(infrastructure_signals, strong_at=3),
                    snippet_text=self._sentence(
                        "Repository evidence indicates containerized infrastructure signals",
                        repo=repo,
                        signals=infrastructure_signals,
                    ),
                    signals=infrastructure_signals,
                )
            )

        testing_signals = self._testing_signals(repo)
        if len(testing_signals) >= 2:
            evidence.append(
                RepositoryEvidence(
                    type="architecture_evidence",
                    title="Repository signal: automated testing",
                    skills=["Pytest", "Testing", "Test Automation"],
                    evidence_strength=self._strength(testing_signals, strong_at=3),
                    snippet_text=self._sentence(
                        "Repository evidence indicates automated testing signals",
                        repo=repo,
                        signals=testing_signals,
                    ),
                    signals=testing_signals,
                )
            )

        ai_workflow_signals = self._ai_workflow_signals(repo)
        if len(ai_workflow_signals) >= 2:
            evidence.append(
                RepositoryEvidence(
                    type="architecture_evidence",
                    title="Repository signal: automation/workflow integration",
                    skills=self._ai_workflow_skills(ai_workflow_signals),
                    evidence_strength=self._strength(ai_workflow_signals, strong_at=3),
                    snippet_text=self._sentence(
                        "Repository evidence indicates automation/workflow integration signals",
                        repo=repo,
                        signals=ai_workflow_signals,
                    ),
                    signals=ai_workflow_signals,
                )
            )

        return evidence

    def _fastapi_architecture_signals(self, repo: "_RepositorySnapshot") -> list[str]:
        return self._signals(
            repo,
            {
                "FastAPI dependency": r"\bfastapi\b",
                "FastAPI(": r"\bFastAPI\s*\(",
                "APIRouter(": r"\bAPIRouter\s*\(",
                "Depends(": r"\bDepends\s*\(",
                "async def": r"\basync\s+def\s+",
                "api routes path": r"(?:^|/)(?:api|routes|routers)(?:/|$)",
            },
        )

    def _has_fastapi_architecture(self, signals: list[str]) -> bool:
        has_fastapi = any(signal in {"FastAPI dependency", "FastAPI("} for signal in signals)
        has_architecture = any(
            signal in {"APIRouter(", "Depends(", "async def", "api routes path"}
            for signal in signals
        )
        return has_fastapi and has_architecture

    def _persistence_layer_signals(self, repo: "_RepositorySnapshot") -> list[str]:
        return self._signals(
            repo,
            {
                "SQLAlchemy": r"\bsqlalchemy\b",
                "AsyncSession": r"\bAsyncSession\b",
                "Alembic": r"\balembic\b",
                "mapped_column": r"\bmapped_column\b",
                "relationship": r"\brelationship\b",
                "PostgreSQL": r"\bpostgres(?:ql)?\b|\basyncpg\b|\bpsycopg\b",
                "migrations path": r"(?:^|/)alembic(?:/|$)|migrations/",
            },
        )

    def _infrastructure_signals(self, repo: "_RepositorySnapshot") -> list[str]:
        return self._signals(
            repo,
            {
                "docker-compose": r"\bdocker-compose\.ya?ml\b|services:\s*\n",
                "Dockerfile": r"\bDockerfile\b|FROM\s+python",
                "Redis": r"\bredis\b",
                "PostgreSQL": r"\bpostgres(?:ql)?\b",
                "Celery": r"\bcelery\b",
            },
        )

    def _testing_signals(self, repo: "_RepositorySnapshot") -> list[str]:
        return self._signals(
            repo,
            {
                "pytest": r"\bpytest\b",
                "tests path": r"(?:^|/)tests(?:/|$)|(?:^|/)test_[^/]+\.py$",
                "TestClient": r"\bTestClient\b",
            },
        )

    def _ai_workflow_signals(self, repo: "_RepositorySnapshot") -> list[str]:
        return self._signals(
            repo,
            {
                "OpenAI": r"\bopenai\b",
                "LangChain": r"\blangchain\b",
                "Telegram": r"\btelegram\b|\baiogram\b|python-telegram-bot",
                "workflow": r"\bworkflow\b|\borchestrat\w+\b|\bpipeline\b",
                "LLM": r"\bllm\b|\bgpt\b|\bchatgpt\b",
                "automation": r"\bautomation\b|automat\w+",
            },
        )

    def _signals(self, repo: "_RepositorySnapshot", patterns: Mapping[str, str]) -> list[str]:
        corpus = repo.corpus
        found: list[str] = []
        for label, pattern in patterns.items():
            if re.search(pattern, corpus, flags=re.IGNORECASE | re.MULTILINE):
                found.append(label)
        return found

    def _strength(self, signals: Sequence[str], *, strong_at: int) -> str:
        return "strong" if len(signals) >= strong_at else "medium"

    def _infra_skill_addons(self, signals: Sequence[str]) -> list[str]:
        addons: list[str] = []
        if "Redis" in signals:
            addons.append("Redis")
        if "PostgreSQL" in signals:
            addons.append("PostgreSQL")
        if "Celery" in signals:
            addons.append("Celery")
        return self._dedupe(addons)

    def _ai_workflow_skills(self, signals: Sequence[str]) -> list[str]:
        skills = ["AI Workflow", "Workflow Orchestration"]
        if "OpenAI" in signals:
            skills.append("OpenAI")
        if "LangChain" in signals:
            skills.append("LangChain")
        if "Telegram" in signals:
            skills.append("Telegram Bot")
        if "LLM" in signals:
            skills.append("LLM")
        if "automation" in signals:
            skills.append("Automation")
        return self._dedupe(skills)

    def _sentence(self, prefix: str, *, repo: "_RepositorySnapshot", signals: Sequence[str]) -> str:
        repo_name = repo.name.strip() or "repository"
        signal_text = ", ".join(signals[:5])
        url = f" Source: {repo.url}" if repo.url else ""
        return f"{prefix} in {repo_name}. Signals: {signal_text}.{url}".strip()

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = re.sub(r"\s+", " ", str(value).strip()).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(str(value).strip())
        return result


@dataclass(frozen=True)
class _RepositorySnapshot:
    name: str
    description: str | None
    url: str | None
    languages: list[str]
    topics: list[str]
    readme_snippet: str | None
    dependency_files: dict[str, str]
    repo_files: list[str]
    source_files: dict[str, str]

    @property
    def corpus(self) -> str:
        parts = [
            self.name,
            self.description or "",
            self.url or "",
            " ".join(self.languages),
            " ".join(self.topics),
            self.readme_snippet or "",
            "\n".join(self.repo_files),
            "\n".join(self.dependency_files.keys()),
            "\n".join(self.dependency_files.values()),
            "\n".join(self.source_files.keys()),
            "\n".join(self.source_files.values()),
        ]
        return "\n".join(part for part in parts if part)
