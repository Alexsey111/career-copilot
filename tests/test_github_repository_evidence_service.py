from __future__ import annotations

from app.services.github_repository_evidence_service import GitHubRepositoryEvidenceService


def test_repository_evidence_service_extracts_neutral_repository_signals() -> None:
    service = GitHubRepositoryEvidenceService()

    evidence = service.analyze_repository(
        name="career-copilot",
        description="AI career copilot backend",
        url="https://github.com/example/career-copilot",
        languages=["Python"],
        topics=["openai", "automation"],
        readme_snippet="OpenAI workflow automation service.",
        dependency_files={
            "pyproject.toml": "fastapi sqlalchemy asyncpg pytest openai",
            "docker-compose.yml": "services:\n  postgres:\n  redis:\n",
            "Dockerfile": "FROM python:3.12",
        },
        repo_files=[
            "app/main.py",
            "app/api/routes/documents.py",
            "app/models/entities.py",
            "alembic/versions/001_init.py",
            "tests/test_documents.py",
        ],
        source_files={
            "app/main.py": "from fastapi import FastAPI\napp = FastAPI()",
            "app/api/routes/documents.py": (
                "from fastapi import APIRouter, Depends\n"
                "from sqlalchemy.ext.asyncio import AsyncSession\n"
                "router = APIRouter()\n"
                "async def create(session: AsyncSession = Depends()): ..."
            ),
            "app/models/entities.py": (
                "from sqlalchemy.orm import mapped_column, relationship\n"
            ),
            "tests/test_documents.py": (
                "import pytest\nfrom fastapi.testclient import TestClient\n"
            ),
        },
    )

    titles = {item["title"] for item in evidence}
    assert "Repository signal: FastAPI/API implementation" in titles
    assert "Repository signal: database persistence" in titles
    assert "Repository signal: containerized infrastructure" in titles
    assert "Repository signal: automated testing" in titles
    assert "Repository signal: automation/workflow integration" in titles

    fastapi = next(
        item
        for item in evidence
        if item["title"] == "Repository signal: FastAPI/API implementation"
    )
    assert fastapi == {
        "type": "architecture_evidence",
        "title": "Repository signal: FastAPI/API implementation",
        "skills": ["FastAPI", "API", "Async API"],
        "evidence_strength": "strong",
        "fact_status": "needs_confirmation",
        "source": "github_repository_analysis",
        "snippet_text": (
            "Repository evidence indicates FastAPI/API implementation signals in career-copilot. "
            "Signals: FastAPI dependency, FastAPI(, APIRouter(, Depends(, async def. "
            "Source: https://github.com/example/career-copilot"
        ),
        "signals": [
            "FastAPI dependency",
            "FastAPI(",
            "APIRouter(",
            "Depends(",
            "async def",
            "api routes path",
        ],
    }

    rendered = "\n".join(
        f"{item['title']} {item['snippet_text']}" for item in evidence
    )
    assert "Implemented FastAPI backend architecture" not in rendered
    assert "Designed PostgreSQL persistence layer" not in rendered
    assert "Implemented AI workflow orchestration" not in rendered


def test_repository_evidence_service_does_not_emit_keyword_only_fastapi_claim() -> None:
    service = GitHubRepositoryEvidenceService()

    evidence = service.analyze_repository(
        name="tiny-api",
        dependency_files={"requirements.txt": "fastapi"},
        repo_files=[],
        source_files={},
    )

    assert evidence == []
