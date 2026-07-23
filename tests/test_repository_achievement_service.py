from __future__ import annotations

import pytest

from app.services.core_service_policy import CORE_SERVICE_INVARIANT
from app.services.repository_achievement_service import (
    RepositoryAchievementGenerationResult,
)
from app.services.repository_achievement_service import RepositoryAchievementService


def test_repository_achievement_service_builds_cautious_contribution_evidence() -> None:
    service = RepositoryAchievementService()

    drafts = service.synthesize_project_drafts(
        [
            {
                "id": "ev-fastapi",
                "title": "Implemented FastAPI backend architecture",
                "skills": ["FastAPI", "Backend Architecture", "Async API"],
                "fact_status": "needs_confirmation",
                "star_summary": {
                    "category": "architecture_evidence",
                    "source": "github_repository_analysis",
                    "project": "career-copilot",
                },
            },
            {
                "id": "ev-ai",
                "title": "Implemented AI workflow orchestration",
                "skills": ["AI Workflow", "Workflow Orchestration", "OpenAI"],
                "fact_status": "needs_confirmation",
                "star_summary": {
                    "category": "architecture_evidence",
                    "source": "github_repository_analysis",
                    "project": "career-copilot",
                },
            },
            {
                "id": "ev-db",
                "title": "Designed PostgreSQL persistence layer",
                "skills": ["PostgreSQL", "SQLAlchemy", "Persistence Layer"],
                "fact_status": "needs_confirmation",
                "star_summary": {
                    "category": "architecture_evidence",
                    "source": "github_repository_analysis",
                    "project": "career-copilot",
                },
            },
        ]
    )

    assert drafts == [
        {
            "title": (
                "GitHub: career-copilot — "
                "Implemented FastAPI backend architecture, "
                "Implemented AI workflow orchestration, "
                "Designed PostgreSQL persistence layer"
            ),
            "skills": [
                "AI Workflow",
                "Async API",
                "Backend Architecture",
                "FastAPI",
                "OpenAI",
                "Persistence Layer",
                "PostgreSQL",
                "SQLAlchemy",
                "Workflow Orchestration",
            ],
            "summary": (
                "Repository evidence from «career-copilot». "
                "Signals: Implemented FastAPI backend architecture; "
                "Implemented AI workflow orchestration; "
                "Designed PostgreSQL persistence layer. "
                "Candidate ownership is unknown and confidence is low. "
                "Requires candidate confirmation before use in resume."
            ),
            "situation": None,
            "task": "Review candidate ownership before using repository signals in documents.",
            "action": (
                "Repository evidence from «career-copilot». "
                "Signals: Implemented FastAPI backend architecture; "
                "Implemented AI workflow orchestration; "
                "Designed PostgreSQL persistence layer. "
                "Candidate ownership is unknown and confidence is low. "
                "Requires candidate confirmation before use in resume."
            ),
            "result": None,
            "fact_status": "needs_confirmation",
            "candidate_ownership": "unknown",
            "candidate_ownership_confidence": "low",
            "requires_confirmation": True,
            "repository_signal": True,
            "source": "github_repository_analysis",
            "source_evidence_ids": ["ev-fastapi", "ev-ai", "ev-db"],
        }
    ]


def test_repository_achievement_payload_requires_candidate_confirmation() -> None:
    service = RepositoryAchievementService()

    draft = service.synthesize_project_drafts(
        [
            {
                "id": "ev-fastapi",
                "title": "Implemented FastAPI backend architecture",
                "skills": ["FastAPI", "Backend Architecture", "Async API"],
                "star_summary": {
                    "category": "architecture_evidence",
                    "project": "career-copilot",
                },
            },
            {
                "id": "ev-ai",
                "title": "Implemented AI workflow orchestration",
                "skills": ["AI Workflow", "Workflow Orchestration", "OpenAI"],
                "star_summary": {
                    "category": "architecture_evidence",
                    "project": "career-copilot",
                },
            },
        ]
    )[0]

    payload = service._draft_to_achievement_payload(draft)

    assert payload["situation"] is None
    assert payload["task"] == (
        "Review candidate ownership before using repository signals in documents."
    )
    assert payload["action"].startswith(
        "Repository evidence from «career-copilot»."
    )
    assert payload["result"] is None
    assert "candidate ownership is unknown" in payload["evidence_note"].lower()
    assert "candidate ownership confidence: low" in payload["evidence_note"].lower()


def test_repository_achievement_service_keeps_core_synthesis_neutral() -> None:
    service = RepositoryAchievementService()

    draft = service.synthesize_project_drafts(
        [
            {
                "id": "ev-fastapi",
                "title": "Implemented FastAPI backend architecture",
                "skills": ["FastAPI", "Backend Architecture"],
                "star_summary": {
                    "category": "architecture_evidence",
                    "project": "career-copilot",
                },
            },
            {
                "id": "ev-ai",
                "title": "Implemented AI workflow orchestration",
                "skills": ["AI Workflow", "Workflow Orchestration"],
                "star_summary": {
                    "category": "architecture_evidence",
                    "project": "career-copilot",
                },
            },
        ]
    )[0]

    generated_narrative = " ".join(
        str(draft.get(field) or "")
        for field in ("title", "situation", "task", "action", "result")
    )

    assert service.engineering_invariant == CORE_SERVICE_INVARIANT
    assert "AI Career Copilot" not in generated_narrative
    assert "pipeline анализа вакансий" not in generated_narrative
    assert "tailored resume" not in generated_narrative
    assert "спроектировать FastAPI backend" not in generated_narrative
    assert draft["candidate_ownership"] == "unknown"
    assert draft["candidate_ownership_confidence"] == "low"
    assert draft["requires_confirmation"] is True
    assert draft["repository_signal"] is True


def test_repository_achievement_service_ignores_non_architecture_evidence() -> None:
    service = RepositoryAchievementService()

    drafts = service.synthesize_project_drafts(
        [
            {
                "id": "ev-project",
                "title": "content-factory",
                "skills": ["Python", "Dockerfile"],
                "star_summary": {"category": "project"},
            }
        ]
    )

    assert drafts == []


def test_repository_achievement_uses_repo_name_from_star_summary() -> None:
    """Bug#4: разные репо должны давать различимые title/summary, чтобы
    пользователь видел, какое достижение подтверждать."""
    service = RepositoryAchievementService()

    drafts_a = service.synthesize_project_drafts(
        [
            {
                "id": "ev-1",
                "title": "Repository signal: FastAPI/API implementation",
                "skills": ["FastAPI"],
                "star_summary": {"project": "alpha", "category": "architecture_evidence"},
            }
        ]
    )
    drafts_b = service.synthesize_project_drafts(
        [
            {
                "id": "ev-2",
                "title": "Repository signal: database persistence",
                "skills": ["PostgreSQL", "SQLAlchemy"],
                "star_summary": {"project": "beta", "category": "architecture_evidence"},
            }
        ]
    )

    assert drafts_a[0]["title"].startswith("GitHub: alpha —")
    assert drafts_b[0]["title"].startswith("GitHub: beta —")
    assert drafts_a[0]["title"] != drafts_b[0]["title"]
    assert "alpha" in drafts_a[0]["summary"]
    assert "beta" in drafts_b[0]["summary"]
    # Конкретные сигналы из title (без префикса "Repository signal: ")
    assert "FastAPI/API implementation" in drafts_a[0]["summary"]
    assert "database persistence" in drafts_b[0]["summary"]


def test_repository_achievement_falls_back_to_snippet_repo_name() -> None:
    """Если ``star_summary.project`` не заполнен — имя репо берём из
    ``snippet_text`` («Repository evidence indicates X in <repo_name>»)."""
    service = RepositoryAchievementService()

    drafts = service.synthesize_project_drafts(
        [
            {
                "id": "ev-1",
                "title": "Repository signal: containerized infrastructure",
                "skills": ["Docker"],
                "snippet_text": (
                    "Repository evidence indicates containerized "
                    "infrastructure signals in my-cool-repo. "
                    "Signals: Dockerfile, docker-compose.yml."
                ),
                "star_summary": {"category": "architecture_evidence"},
            }
        ]
    )

    assert drafts[0]["title"].startswith("GitHub: my-cool-repo —")
    assert "my-cool-repo" in drafts[0]["summary"]


class _NoResumeExtractionRepository:
    async def get_latest_for_active_source_file_kind(self, *args, **kwargs):
        raise AssertionError("repository achievement generation must not require resume")


class _EmptyEvidenceRepository:
    async def list_by_user_id(self, *args, **kwargs):
        return []


class _NoopAchievementRepository:
    async def append_for_profile(self, *args, **kwargs):
        return []

    async def list_for_profile(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
async def test_repository_achievement_generation_does_not_assume_resume_exists(
    db_session,
    test_user,
) -> None:
    service = RepositoryAchievementService(
        evidence_repository=_EmptyEvidenceRepository(),
        achievement_repository=_NoopAchievementRepository(),
        file_extraction_repository=_NoResumeExtractionRepository(),
    )

    result = await service.generate_repository_achievement_drafts(
        db_session,
        user_id=test_user.id,
        profile_id=test_user.id,
    )

    assert isinstance(result, RepositoryAchievementGenerationResult)
    assert result.extraction_id is None
    assert result.achievements == []
    assert result.warnings == ["no github repository evidence found"]
