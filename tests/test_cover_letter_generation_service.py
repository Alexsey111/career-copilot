from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import AIOrchestrator
from app.ai.clients.base import BaseLLMClient
from app.services.cover_letter_generation_service import (
    CoverLetterGenerationService,
    PROJECT_DISPLAY_HINTS,
)
from app.services.resume_renderer import render_cover_letter


class MockCoverLetterClient(BaseLLMClient):
    """Mock LLM client для тестов cover letter enhancement."""

    def __init__(self, enhanced_text: str | None = None):
        self.enhanced_text = enhanced_text

    async def aclose(self):
        pass

    async def generate(self, prompt: str, **kwargs):
        return {
            "content": "ok",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": kwargs.get("model"),
        }

    async def generate_structured(self, prompt: str, output_schema: dict, **kwargs):
        return {
            "content": {"enhanced_text": self.enhanced_text or "Enhanced cover letter text"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": kwargs.get("model"),
        }

    @property
    def provider_name(self):
        return "mock"


def test_cover_letter_build_draft_includes_strengths_and_gaps() -> None:
    """Тест что _build_draft создаёт черновик с strengths, gaps и achievements."""
    service = CoverLetterGenerationService()

    draft = service._build_draft(
        vacancy_title="Backend Developer",
        company="TestCo",
        strengths=["Python", "Docker"],
        gaps=["FastAPI", "Redis"],
        achievements=["Built AI system"],
    )

    assert "Backend Developer" in draft
    assert "TestCo" in draft
    assert "Python" in draft
    assert "Docker" in draft
    assert "FastAPI" in draft
    assert "Redis" in draft
    assert "Built AI system" in draft
    assert "still developing experience" in draft.lower()
    assert "I would welcome the opportunity" in draft


def test_cover_letter_build_draft_handles_empty_gaps() -> None:
    service = CoverLetterGenerationService()

    draft = service._build_draft(
        vacancy_title="Backend Developer",
        company="TestCo",
        strengths=["Python"],
        gaps=[],
        achievements=[],
    )

    assert "Backend Developer" in draft
    assert "Python" in draft
    assert "while I am still developing" not in draft.lower()


@pytest.mark.asyncio
async def test_cover_letter_ai_enhancement_returns_enhanced_text(db_session: AsyncSession, test_user):
    """Тест что AI enhancement возвращает улучшенный текст."""
    # Текст с повторяющимися ключевыми словами чтобы пройти проверку
    original_text = """I am applying for the Backend Developer position at Test Company.
My experience includes Python development and Docker containerization.
I have built several projects using these technologies.
I am excited about this opportunity."""
    
    enhanced_text = """I am applying for the Backend Developer position at Test Company.
My professional experience includes Python development and Docker containerization.
I have successfully built several projects using these technologies.
I am excited about this opportunity to join your team."""
    
    class EnhancedClient(MockCoverLetterClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {"enhanced_text": enhanced_text},
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=EnhancedClient())
    service = CoverLetterGenerationService()
    service.ai_orchestrator = orchestrator

    result = await service.enhance_cover_letter_with_ai(
        session=db_session,
        user_id=test_user.id,
        draft_text=original_text,
    )

    assert result == enhanced_text


@pytest.mark.asyncio
async def test_cover_letter_safety_rejects_gaps_removal(db_session: AsyncSession, test_user):
    """Тест что удаление gaps отклоняется и возвращается оригинал."""

    original_text = """I am applying for the Backend Developer role at TestCo.

My experience aligns well with your requirements, including: Python, Docker.

While I am still developing experience in FastAPI, Redis, I have been actively working to strengthen these areas.

I would welcome the opportunity to contribute to your team."""

    class GapsRemovingClient(MockCoverLetterClient):
        async def generate_structured(self, *args, **kwargs):
            # Удаляет все gaps из текста
            return {
                "content": {
                    "enhanced_text": "I am applying for the Backend Developer role. I have all required skills.",
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=GapsRemovingClient())
    service = CoverLetterGenerationService()
    service.ai_orchestrator = orchestrator

    result = await service.enhance_cover_letter_with_ai(
        session=db_session,
        user_id=test_user.id,
        draft_text=original_text,
    )

    # FastAPI и Redis были удалены AI → фолбэк на оригинал
    assert result == original_text
    assert "FastAPI" in result
    assert "Redis" in result


def test_cover_letter_generation_uses_analysis_strengths_and_gaps_as_truth() -> None:
    service = CoverLetterGenerationService()

    matched, missing = service._extract_match_keywords_from_analysis(
        strengths_json=[
            {"keyword": "Python", "scope": "must_have"},
            {"keyword": "Docker", "scope": "nice_to_have"},
        ],
        gaps_json=[
            {"keyword": "FastAPI", "scope": "must_have"},
            {"keyword": "Redis", "scope": "nice_to_have"},
        ],
    )

    assert matched == ["Python", "Docker"]
    assert missing == ["FastAPI", "Redis"]


def test_cover_letter_relevance_paragraph_does_not_include_missing_keywords() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["Python"],
        selected_achievements=[],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )

    assert "Python" in paragraph
    assert "Redis" not in paragraph
    assert "PostgreSQL" not in paragraph
    assert "backend/API-разработки" in paragraph
    assert "confirmed overlap" not in paragraph


def test_cover_letter_relevance_paragraph_uses_extracted_evidence() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["AI workflow", "automation"],
        selected_achievements=[],
        selected_evidence=[
            {
                "evidence_id": "ev-1",
                "title": "ИИ-система мониторинга безопасности",
                "source_type": "resume_structured",
                "skills": ["AI", "computer vision", "monitoring"],
                "fact_status": "user_provided",
                "evidence_strength": "medium",
                "reason": "2 skill matches, user-provided",
            }
        ],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="AI Automation Specialist",
    )

    assert "автоматизации workflow" in paragraph
    assert "подтверждённый контекст обработки визуальных данных" in paragraph
    assert "извлечённые факты из резюме" not in paragraph
    assert "computer vision" not in paragraph


def test_cover_letter_project_context_is_domain_neutral_for_visual_monitoring() -> None:
    service = CoverLetterGenerationService()

    context = service._cover_letter_project_phrase(
        title="Computer vision monitoring",
        body="Image and video workflow for quality control",
        skills=["computer vision", "python"],
        fact_status="confirmed",
        ownership_confidence="high",
        requires_confirmation=False,
    )

    assert context == "подтверждённый контекст обработки визуальных данных"
    assert "пвх" not in context.lower()
    assert "пансионат" not in context.lower()
    assert "career copilot" not in context.lower()


def test_cover_letter_project_display_hints_are_neutral() -> None:
    assert PROJECT_DISPLAY_HINTS["career-copilot"] == "backend workflow evidence"
    assert PROJECT_DISPLAY_HINTS["content-factory"] == "automation workflow evidence"


def test_cover_letter_relevance_paragraph_avoids_buzzword_list_and_fabricated_role() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["LLM", "ChatGPT", "Automation", "AI Workflow", "No-code"],
        selected_achievements=[
            {
                "title": "AI Career Copilot",
                "action": "Built backend for vacancy analysis and tailored resume generation.",
                "fact_status": "confirmed",
            }
        ],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="AI Automation Specialist",
    )

    assert "LLM, ChatGPT, Automation" not in paragraph
    assert "AI-assisted процессов" in paragraph
    assert "backend-системы" not in paragraph
    assert "подтверждённый проектный контекст" in paragraph
    assert "качестве конкретного вклада" in paragraph


def test_cover_letter_blocks_unconfirmed_evidence_from_strong_project_phrase() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["FastAPI", "PostgreSQL"],
        selected_achievements=[
            {
                "title": "Repository evidence: backend-related implementation signals",
                "action": "Repository evidence indicates backend-related implementation signals.",
                "fact_status": "needs_confirmation",
                "candidate_ownership_confidence": "low",
                "requires_confirmation": True,
            }
        ],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )

    assert "опыт проектирования backend/API" not in paragraph
    assert "backend-системы" not in paragraph
    assert "подтверждаемый проектный контекст" in paragraph


def test_cover_letter_evidence_phrases_render_human_readable_project_context() -> None:
    service = CoverLetterGenerationService()

    phrases = service._build_evidence_relevance_phrases(
        selected_evidence=[
            {
                "evidence_id": "ev-1",
                "title": "content-factory",
                "source_type": "github_public",
                "skills": ["Technologies: Python", "HTML", "Mako", "OpenAI"],
            },
            {
                "evidence_id": "ev-2",
                "title": "Technology stack from resume",
                "source_type": "resume_structured",
                "skills": ["chatgpt", "llm", "Dockerfile", "AI workflow"],
            },
        ],
        selected_achievements=[],
    )

    assert phrases == [
        "content-factory — automation workflow evidence (Python, OpenAI)",
        "ChatGPT, LLM, AI Workflow",
    ]


def test_cover_letter_alignment_sections_are_evidence_grounded() -> None:
    service = CoverLetterGenerationService()

    selected_evidence = [
        {
            "evidence_id": "ev-1",
            "title": "Prompt Engineering",
            "source_type": "resume_structured",
            "skills": ["ChatGPT", "LLM", "prompt engineering"],
            "fact_status": "user_provided",
            "evidence_strength": "medium",
            "reason": "required skill matches",
        }
    ]

    relevance = service._build_evidence_relevance(
        selected_evidence=selected_evidence,
        selected_achievements=[],
    )
    alignment = service._build_vacancy_alignment(
        matched_keywords=["prompt engineering"],
        selected_evidence=selected_evidence,
        selected_achievements=[],
    )

    assert relevance == [
        {
            "evidence_id": "ev-1",
            "title": "Prompt Engineering",
            "source_type": "resume_structured",
            "fact_status": "user_provided",
            "evidence_strength": "medium",
            "skills": ["ChatGPT", "LLM", "prompt engineering"],
            "reason": "required skill matches",
        }
    ]
    assert alignment[0]["coverage"] == "evidence_grounded"
    assert alignment[0]["evidence_title"] == "Prompt Engineering"


def test_cover_letter_warnings_keep_missing_keywords_out_of_rendered_letter() -> None:
    content_json = {
        "sections": {
            "opening": "Здравствуйте!\n\nРассматриваю вакансию Backend Developer.",
            "relevance_paragraph": (
                "По текущему профилю наиболее подтверждённое пересечение "
                "с вакансией: Python."
            ),
            "closing": "Буду рад обсудить, как мой опыт может быть полезен.",
            "warnings": [
                "profile does not strongly support these vacancy keywords yet: Redis, PostgreSQL"
            ],
        }
    }

    rendered = render_cover_letter(content_json)

    assert "Python" in rendered
    assert "Здравствуйте" in rendered
    assert "Буду рад обсудить" in rendered
    assert "profile does not strongly support" not in rendered
    assert "Redis" not in rendered
    assert "PostgreSQL" not in rendered


def test_cover_letter_rendered_text_is_russian_and_not_internal_copy() -> None:
    service = CoverLetterGenerationService()

    opening = service._build_opening(
        full_name="Перминов Алексей",
        vacancy_title="Backend Developer",
        company="Test Company",
        headline="Prompt Engineering, Data Science, Vibe-coding",
    )
    relevance = service._build_relevance_paragraph(
        matched_keywords=["Python"],
        selected_achievements=[
            {
                "title": "Создание ИИ-системы для мониторинга безопасности",
                "fact_status": "needs_confirmation",
                "reason": "ai_relevance",
            }
        ],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )
    closing = service._build_closing(
        vacancy_title="Backend Developer",
        company="Test Company",
    )

    rendered = render_cover_letter(
        {
            "sections": {
                "opening": opening,
                "relevance_paragraph": relevance,
                "closing": closing,
                "warnings": [],
            }
        }
    )

    assert "Здравствуйте" in rendered
    assert "Меня зовут Перминов Алексей" in rendered
    assert "Роль Backend Developer" in rendered
    assert "В требованиях вижу совпадение" in rendered
    assert "Буду рад обсудить" in rendered

    assert "Dear hiring team" not in rendered
    assert "Thank you for your consideration" not in rendered
    assert "confirmed overlap" not in rendered
    assert "needs_confirmation" not in rendered


def test_cover_letter_generation_uses_only_confirmed_achievement_titles() -> None:
    service = CoverLetterGenerationService()

    achievements = [
        SimpleNamespace(
            title="Подтверждённый AI-проект",
            fact_status="confirmed",
        ),
        SimpleNamespace(
            title="Неподтверждённый проект",
            fact_status="needs_confirmation",
        ),
        SimpleNamespace(
            title="",
            fact_status="confirmed",
        ),
    ]

    titles = service._get_confirmed_achievement_titles(achievements)

    assert titles == ["Подтверждённый AI-проект"]


def test_cover_letter_selected_achievements_are_confirmed_and_do_not_create_claims() -> None:
    service = CoverLetterGenerationService()

    selected = service._select_relevant_achievements(
        achievements=[
            {
                "title": "Подтверждённый AI-проект",
                "fact_status": "confirmed",
                "situation": "Нужно было сократить время подготовки отчётов",
                "task": "Автоматизировать генерацию аналитики",
                "action": "Собрал pipeline и внедрил AI-assisted workflow",
                "result": "Сократил ручную работу на 70%",
                "metric_text": "ручная работа -70%",
            }
        ],
        keywords=["Python"],
    )

    assert selected == [
        {
            "title": "Подтверждённый AI-проект",
            "fact_status": "confirmed",
            "reason": "ai_relevance",
            "situation": "Нужно было сократить время подготовки отчётов",
            "task": "Автоматизировать генерацию аналитики",
            "action": "Собрал pipeline и внедрил AI-assisted workflow",
            "result": "Сократил ручную работу на 70%",
            "metric_text": "ручная работа -70%",
        }
    ]

    claims = service._build_claims_needing_confirmation(
        selected_achievements=selected,
    )

    assert claims == []
