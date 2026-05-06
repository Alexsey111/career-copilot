from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import AIOrchestrator
from app.ai.clients.base import BaseLLMClient
from app.services.cover_letter_generation_service import CoverLetterGenerationService


class MockCoverLetterClient(BaseLLMClient):
    """Mock LLM client для тестов cover letter enhancement."""

    def __init__(self, enhanced_text: str | None = None):
        self.enhanced_text = enhanced_text

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
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )

    assert "Python" in paragraph
    assert "Redis" not in paragraph
    assert "PostgreSQL" not in paragraph
    assert "подтверждённое пересечение" in paragraph
    assert "confirmed overlap" not in paragraph


def test_cover_letter_warnings_keep_missing_keywords_out_of_rendered_letter() -> None:
    service = CoverLetterGenerationService()

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

    rendered = service._render_cover_letter(content_json)

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
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )
    closing = service._build_closing(
        vacancy_title="Backend Developer",
        company="Test Company",
    )

    rendered = service._render_cover_letter(
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
    assert "Рассматриваю вакансию Backend Developer" in rendered
    assert "По текущему профилю" in rendered
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
        achievement_titles=["Подтверждённый AI-проект"],
        keywords=["Python"],
    )

    assert selected == [
        {
            "title": "Подтверждённый AI-проект",
            "fact_status": "confirmed",
            "reason": "ai_relevance",
        }
    ]

    claims = service._build_claims_needing_confirmation(
        selected_achievements=selected,
    )

    assert claims == []
