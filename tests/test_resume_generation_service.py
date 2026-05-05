from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ai.orchestrator import AIOrchestrator
from app.api.ai.clients.base import BaseLLMClient
from app.services.resume_generation_service import ResumeGenerationService


class MockResumeClient(BaseLLMClient):
    """Mock LLM client для тестов resume enhancement."""

    def __init__(self, enhanced_text: str = "Enhanced: Built robust API with Python"):
        self.enhanced_text = enhanced_text

    async def generate(self, prompt: str, **kwargs):
        return {
            "content": "ok",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": kwargs.get("model"),
        }

    async def generate_structured(self, prompt: str, output_schema: dict, **kwargs):
        return {
            "content": {"enhanced_text": self.enhanced_text},
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": kwargs.get("model"),
        }

    @property
    def provider_name(self):
        return "mock"


@pytest.mark.asyncio
async def test_resume_enhancement_with_ai(db_session: AsyncSession, test_user):
    """Тест что enhance_resume_with_ai вызывает AI оркестратор и возвращает улучшенный текст."""
    # Более длинный оригинал, чтобы улучшения проходили проверку безопасности
    original_text = """Built a REST API with Python and FastAPI.
Implemented user authentication and authorization.
Integrated with PostgreSQL database for data persistence."""
    
    enhanced_text = """Built a robust REST API with Python and FastAPI.
Implemented secure user authentication and authorization.
Integrated with PostgreSQL database for efficient data persistence."""
    
    client = MockResumeClient(enhanced_text=enhanced_text)
    orchestrator = AIOrchestrator(client=client)
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    enhanced = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original_text,
    )

    assert isinstance(enhanced, str)
    assert "robust" in enhanced
    assert "secure" in enhanced


@pytest.mark.asyncio
async def test_resume_enhancement_rejects_bad_output(db_session: AsyncSession, test_user):
    """Тест что небезопасное улучшение отклоняется и возвращается оригинал."""

    class BadClient(MockResumeClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {
                    "enhanced_text": "Short",  # Слишком коротко по сравнению с оригиналом
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=BadClient())
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    # Оригинальный текст с ~37 словами, BadClient вернёт 1 слово (< 50%)
    original = """Built a robust REST API with Python and FastAPI.
Implemented secure user authentication and authorization.
Integrated with PostgreSQL database for efficient data persistence.
Added comprehensive error handling and logging."""

    result = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original,
    )

    assert result == original


@pytest.mark.asyncio
async def test_resume_enhancement_rejects_lost_keywords(db_session: AsyncSession, test_user):
    """Тест что потеря ключевых слов (>4 символов) отклоняется."""

    class KeywordLosingClient(MockResumeClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {
                    # Убраны ключевые слова: Python, FastAPI, PostgreSQL
                    "enhanced_text": "Built improved backend systems with authentication and logging.",
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=KeywordLosingClient())
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    original = """Built a robust REST API with Python and FastAPI.
Implemented secure user authentication and authorization.
Integrated with PostgreSQL database for efficient data persistence."""

    result = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original,
    )

    # Ключевые слова Python, FastAPI, PostgreSQL потеряны → фолбэк на оригинал
    assert result == original
    assert "Python" in result
    assert "FastAPI" in result


@pytest.mark.asyncio
async def test_resume_enhancement_in_russian(db_session: AsyncSession, test_user):
    """Тест что AI enhancement работает с русским языком."""

    original = "Python Developer с опытом создания REST API"

    class RussianClient(MockResumeClient):
        async def generate_structured(self, *args, **kwargs):
            # Сохраняем ключевые слова (Python, API) чтобы пройти проверку безопасности
            return {
                "content": {
                    "enhanced_text": "Python Developer с богатым опытом создания надежных REST API",
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=RussianClient())
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    result = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original,
        language="ru",
    )

    # Ключевые слова Python и API сохранены, добавлены улучшения
    assert "Python" in result
    assert "API" in result
    assert "богатым" in result or "надежных" in result


def test_resume_generation_extracts_match_keywords_from_analysis_json() -> None:
    service = ResumeGenerationService()

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


def test_resume_generation_skill_matching_does_not_overclaim_specific_db() -> None:
    service = ResumeGenerationService()

    assert service._skill_matches_keyword("SQL", "PostgreSQL") is False
    assert service._skill_matches_keyword("PostgreSQL", "SQL") is True
    assert service._skill_matches_keyword("API", "FastAPI") is False
    assert service._skill_matches_keyword("FastAPI", "API") is True


def test_resume_generation_selects_matched_skills_first_without_claiming_gaps() -> None:
    service = ResumeGenerationService()

    selected = service._select_resume_skills(
        raw_skills=["Python", "SQL", "API", "Docker", "LLM"],
        matched_keywords=["Python", "Docker"],
    )

    assert selected[:2] == ["Python", "Docker"]
    assert "SQL" in selected
    assert "API" in selected


def test_resume_rendered_text_does_not_include_internal_review_notes() -> None:
    service = ResumeGenerationService()

    rendered = service._render_resume_text(
        {
            "candidate": {
                "full_name": "Test User",
                "headline": "AI Product Engineer",
                "location": "Remote",
            },
            "target_vacancy": {
                "title": "Backend Developer",
            },
            "sections": {
                "summary_bullets": [
                    "Подтверждённые пересечения с вакансией Backend Developer: Python."
                ],
                "skills": ["Python", "Docker"],
                "experience": [],
                "selected_achievements": [
                    {
                        "title": "Создание ИИ-системы для мониторинга безопасности",
                        "fact_status": "needs_confirmation",
                    }
                ],
                "warnings": ["missing or weakly represented vacancy keywords: FastAPI"],
                "fit_summary": {"match_score": 27},
            },
        }
    )

    assert "Test User" in rendered
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in rendered
    assert "КРАТКОЕ РЕЗЮМЕ" in rendered
    assert "КЛЮЧЕВЫЕ НАВЫКИ" in rendered
    assert "РЕЛЕВАНТНЫЕ ПРОЕКТЫ" in rendered

    assert "SUMMARY" not in rendered
    assert "SKILLS" not in rendered
    assert "EXPERIENCE" not in rendered
    assert "REVIEW NOTES" not in rendered
    assert "FIT SUMMARY" not in rendered
    assert "Match score" not in rendered
    assert "missing or weakly represented" not in rendered
    assert "needs_confirmation" not in rendered


def test_resume_summary_bullets_are_russian_and_not_internal_copy() -> None:
    service = ResumeGenerationService()

    profile = SimpleNamespace(
        headline="Prompt Engineering, Data Science, Vibe-coding",
        experiences=[],
    )

    bullets = service._build_summary_bullets(
        profile=profile,
        vacancy_title="Backend Developer",
        selected_skills=["Python", "Git", "LLM"],
        selected_achievements=[
            {
                "title": "Создание ИИ-системы для мониторинга безопасности",
                "fact_status": "needs_confirmation",
                "reason": "ai_relevance",
            }
        ],
        matched_keywords=["Python"],
    )

    joined = "\n".join(bullets)

    assert "Профессиональный фокус" in joined
    assert "Подтверждённые пересечения" in joined
    assert "Дополнительные навыки" in joined
    assert "Проектный опыт" in joined

    assert "Candidate profile aligned" not in joined
    assert "Profile-confirmed" not in joined
    assert "Broader skill base" not in joined
    assert "Relevant project experience" not in joined
    assert "Recent role" not in joined


def test_resume_skill_cleanup_trims_noisy_pdf_layout_fragments() -> None:
    service = ResumeGenerationService()

    skills = service._split_skill_text(
        "Python, Git, Искусственный интеллект, LLM, "
        "Нейросети Прошел 3 стажировки по (промптинг), API, SQL"
    )

    assert skills == [
        "Python",
        "Git",
        "Искусственный интеллект",
        "LLM",
        "Нейросети",
        "API",
        "SQL",
    ]


def test_resume_filters_low_confidence_experience_from_noisy_layout() -> None:
    service = ResumeGenerationService()

    assert service._looks_like_low_confidence_experience_item(
        {
            "company": "(ООО «СГЦ ОПЕКА») 2. Автоматизированный Алтайский Государственный Медицинский ИИ-контроль качества Университет",
            "role": "электромонтер по ремонту и ПВХ оконных изделий обслуживанию электрооборудования по изображениям и",
            "description_raw": "video layout noise",
        }
    )



def test_resume_generation_uses_only_confirmed_achievement_titles() -> None:
    service = ResumeGenerationService()

    achievements = [
        SimpleNamespace(
            title="?????????????? AI-??????",
            fact_status="confirmed",
        ),
        SimpleNamespace(
            title="???????????????? ??????",
            fact_status="needs_confirmation",
        ),
        SimpleNamespace(
            title="",
            fact_status="confirmed",
        ),
    ]

    titles = service._get_confirmed_achievement_titles(achievements)

    assert titles == ["?????????????? AI-??????"]


def test_resume_selected_achievements_are_confirmed_and_do_not_create_claims() -> None:
    service = ResumeGenerationService()

    selected = service._select_relevant_achievements(
        achievement_titles=["?????????????? AI-??????"],
        keywords=["Python"],
    )

    assert selected == [
        {
            "title": "?????????????? AI-??????",
            "fact_status": "confirmed",
            "reason": "ai_relevance",
        }
    ]

    claims = service._build_claims_needing_confirmation(
        profile=SimpleNamespace(full_name="Test User"),
        selected_achievements=selected,
    )

    assert claims == []
