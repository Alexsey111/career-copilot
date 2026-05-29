from __future__ import annotations

import base64

import httpx
import pytest

from app.services.github_public_import_service import GitHubPublicImportService


API_PREFIX = "/api/v1"


class _FakeGitHubResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url: str, params=None):
        if url.endswith("/users/alex-ai/repos"):
            return _FakeGitHubResponse(
                [
                    {
                        "name": "ai-vacancy-bot",
                        "full_name": "alex-ai/ai-vacancy-bot",
                        "description": "Telegram bot for AI vacancy automation with OpenAI and FastAPI.",
                        "html_url": "https://github.com/alex-ai/ai-vacancy-bot",
                        "languages_url": "https://api.github.com/repos/alex-ai/ai-vacancy-bot/languages",
                        "topics": ["telegram-bot", "openai", "automation"],
                        "fork": False,
                    }
                ]
            )
        if url.endswith("/languages"):
            return _FakeGitHubResponse({"Python": 1200, "Dockerfile": 80})
        if url.endswith("/readme"):
            readme = "# AI Vacancy Bot\nUses LangChain, workflow automation and Docker."
            return _FakeGitHubResponse(
                {"content": base64.b64encode(readme.encode()).decode()}
            )
        if url.endswith("/contents/pyproject.toml"):
            pyproject = (
                "[project]\n"
                "dependencies = [\"fastapi\", \"sqlalchemy\", \"pytest\", \"openai\"]\n"
            )
            return _FakeGitHubResponse(
                {"content": base64.b64encode(pyproject.encode()).decode()}
            )
        if url.endswith("/contents/requirements.txt"):
            requirements = "redis\nasyncpg\naiogram\n"
            return _FakeGitHubResponse(
                {"content": base64.b64encode(requirements.encode()).decode()}
            )
        if url.endswith("/contents/requirements-dev.txt"):
            return _FakeGitHubResponse({}, status_code=404)
        if url.endswith("/contents/docker-compose.yml"):
            compose = "services:\n  api:\n    image: python:3.12\n  postgres:\n    image: postgres\n"
            return _FakeGitHubResponse(
                {"content": base64.b64encode(compose.encode()).decode()}
            )
        if url.endswith("/contents/docker-compose.yaml"):
            return _FakeGitHubResponse({}, status_code=404)
        if url.endswith("/contents/Dockerfile"):
            dockerfile = "FROM python:3.12\nRUN pip install fastapi\n"
            return _FakeGitHubResponse(
                {"content": base64.b64encode(dockerfile.encode()).decode()}
            )
        if url.endswith("/contents/app/main.py"):
            source = (
                "from fastapi import FastAPI\n\n"
                "app = FastAPI()\n"
            )
            return _FakeGitHubResponse(
                {"content": base64.b64encode(source.encode()).decode()}
            )
        if url.endswith("/contents/app/api/routes/bot.py"):
            source = (
                "from fastapi import APIRouter, Depends\n"
                "from sqlalchemy.ext.asyncio import AsyncSession\n\n"
                "router = APIRouter()\n\n"
                "async def get_session() -> AsyncSession: ...\n"
                "@router.post('/bot')\n"
                "async def run_bot(session: AsyncSession = Depends(get_session)): ...\n"
            )
            return _FakeGitHubResponse(
                {"content": base64.b64encode(source.encode()).decode()}
            )
        if url.endswith("/contents/alembic/versions/001_init.py"):
            source = "from alembic import op\nimport sqlalchemy as sa\n"
            return _FakeGitHubResponse(
                {"content": base64.b64encode(source.encode()).decode()}
            )
        if url.endswith("/contents/tests/test_bot.py"):
            source = (
                "import pytest\n"
                "from fastapi.testclient import TestClient\n\n"
                "def test_bot(): ...\n"
            )
            return _FakeGitHubResponse(
                {"content": base64.b64encode(source.encode()).decode()}
            )
        if url.endswith("/git/trees/HEAD"):
            return _FakeGitHubResponse(
                {
                    "tree": [
                        {"path": "app/main.py"},
                        {"path": "app/api/routes/bot.py"},
                        {"path": "tests/test_bot.py"},
                        {"path": "alembic/versions/001_init.py"},
                    ]
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")


class _UnavailableGitHubAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url: str, params=None):
        raise httpx.ConnectError("Temporary failure in name resolution")


@pytest.mark.asyncio
async def test_github_public_profile_import_creates_unconfirmed_evidence(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.github_public_import_service.httpx.AsyncClient",
        _FakeAsyncClient,
    )

    response = await client.post(
        f"{API_PREFIX}/profile/intake/github-public",
        json={
            "profile_url": "https://github.com/alex-ai",
            "target_role": "AI Automation Developer",
            "max_repositories": 5,
            "include_readme": True,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "github_public"
    assert payload["project_count"] == 1
    assert payload["evidence_snippet_count"] >= 2
    assert "GITHUB PUBLIC PROFILE IMPORT" in payload["raw_text_preview"]
    assert "Python" in payload["technologies"]

    bank_response = await client.get(f"{API_PREFIX}/evidence/bank")
    assert bank_response.status_code == 200, bank_response.text
    bank = bank_response.json()
    project = next(item for item in bank["project_evidence"] if item["title"] == "ai-vacancy-bot")
    assert project["source_type"] == "github_public"
    assert project["fact_status"] == "needs_confirmation"
    assert "Python" in project["skills"]
    assert project["evidence_strength"] == "strong"
    assert "FastAPI" in project["skills"]
    assert "Docker" in project["skills"]
    assert "Pytest" in project["skills"]
    assert "Redis" in project["skills"]
    assert "PostgreSQL" in project["skills"]
    assert "OpenAI" in project["skills"] or "openai" in project["skills"]

    signal = next(
        item
        for item in bank["competency_signals"]
        if item["title"] == "ai-vacancy-bot signals"
    )
    assert signal["source_type"] == "github_public"
    assert signal["fact_status"] == "needs_confirmation"
    assert any("automation" in skill.lower() for skill in signal["skills"])

    architecture = next(
        item
        for item in bank["project_evidence"]
        if item["title"] == "Repository signal: FastAPI/API implementation"
    )
    assert architecture["source_type"] == "github_public"
    assert architecture["fact_status"] == "needs_confirmation"
    assert architecture["evidence_strength"] == "strong"
    assert architecture["star_summary"]["source"] == "github_repository_analysis"
    assert architecture["star_summary"]["category"] == "architecture_evidence"
    assert "API" in architecture["skills"]
    assert "Async API" in architecture["skills"]
    assert "Implemented FastAPI backend architecture" not in architecture["snippet_text"]


@pytest.mark.asyncio
async def test_github_public_profile_import_returns_502_when_github_unavailable(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.github_public_import_service.httpx.AsyncClient",
        _UnavailableGitHubAsyncClient,
    )

    response = await client.post(
        f"{API_PREFIX}/profile/intake/github-public",
        json={
            "profile_url": "https://github.com/alex-ai",
            "target_role": "AI Automation Developer",
            "max_repositories": 5,
            "include_readme": True,
        },
    )

    assert response.status_code == 502, response.text
    assert "GitHub API is temporarily unavailable" in response.json()["detail"]


def test_github_public_username_parser_rejects_non_github_url() -> None:
    service = GitHubPublicImportService()

    with pytest.raises(ValueError):
        service._extract_username("https://example.com/alex-ai")
