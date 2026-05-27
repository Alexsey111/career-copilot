from __future__ import annotations

from app.services.repository_achievement_service import RepositoryAchievementService


def test_repository_achievement_service_synthesizes_project_draft() -> None:
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
            "title": "Разработка AI workflow orchestration системы",
            "skills": [
                "FastAPI",
                "OpenAI",
                "AI Workflow",
                "Workflow Orchestration",
                "Backend Architecture",
                "Async API",
                "PostgreSQL",
                "SQLAlchemy",
                "Persistence Layer",
            ],
            "summary": (
                "На основе GitHub repository evidence по проекту career-copilot "
                "синтезирован проектный черновик: "
                "Implemented FastAPI backend architecture; "
                "Implemented AI workflow orchestration; "
                "Designed PostgreSQL persistence layer "
                "Ключевые навыки: FastAPI, OpenAI, AI Workflow, "
                "Workflow Orchestration, Backend Architecture, Async API "
                "Требует подтверждения кандидатом перед использованием в документах."
            ),
            "situation": (
                "Нужно было собрать инженерную основу проекта AI Career Copilot, "
                "где backend, AI workflow и review-процессы должны работать как "
                "единый продуктовый pipeline."
            ),
            "task": (
                "Задача: спроектировать FastAPI backend, подготовить persistence layer, "
                "связать AI orchestration flow."
            ),
            "action": (
                "Спроектировал FastAPI backend для AI Career Copilot, включающий "
                "pipeline анализа вакансий, генерацию tailored resume и workflow review. "
                "описал PostgreSQL/SQLAlchemy persistence layer для хранения документов, "
                "evidence и workflow-состояний."
            ),
            "result": (
                "Получился review-ready проектный нарратив, который связывает repository "
                "evidence с инженерными capability. Его можно использовать в резюме как "
                "evidence-backed backend/AI workflow experience."
            ),
            "fact_status": "needs_confirmation",
            "source": "github_repository_analysis",
            "source_evidence_ids": ["ev-fastapi", "ev-ai", "ev-db"],
        }
    ]


def test_repository_achievement_payload_uses_star_narrative() -> None:
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

    assert payload["situation"].startswith(
        "Нужно было собрать инженерную основу проекта AI Career Copilot"
    )
    assert "спроектировать FastAPI backend" in payload["task"]
    assert "pipeline анализа вакансий" in payload["action"]
    assert "evidence-backed backend/AI workflow experience" in payload["result"]


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
