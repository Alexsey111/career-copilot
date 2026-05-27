from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import AIOrchestrator
from app.ai.clients.base import BaseLLMClient
from app.services.resume_generation_service import ResumeGenerationService
from app.services.resume_renderer import render_resume


class MockResumeClient(BaseLLMClient):
    """Mock LLM client для тестов resume enhancement."""

    def __init__(self, enhanced_text: str = "Enhanced: Built robust API with Python"):
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
async def test_resume_enhancement_rejects_loss_of_protected_terms(
    db_session: AsyncSession,
    test_user,
):
    """Тест что protected tech terms должны сохраниться в enhanced text."""

    class ProtectedTermLosingClient(MockResumeClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {
                    "enhanced_text": (
                        "Built secure backend services with observability, testing, "
                        "and access controls for user flows."
                    ),
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=ProtectedTermLosingClient())
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    original = """Built secure backend services with Python, FastAPI, PostgreSQL, Redis,
Docker, Kubernetes, AWS, LLM, and SQLAlchemy for user authentication and authorization."""

    result = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original,
    )

    assert result == original
    assert "Python" in result
    assert "FastAPI" in result
    assert "SQLAlchemy" in result


@pytest.mark.asyncio
async def test_resume_enhancement_accepts_semantic_retention(
    db_session: AsyncSession,
    test_user,
):
    """Тест что семантические замены auth/access control проходят safety check."""

    class SemanticRetentionClient(MockResumeClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {
                    "enhanced_text": (
                        "Built secure user auth and access control flows for backend "
                        "services with observability and testing."
                    ),
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=SemanticRetentionClient())
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    original = """Built secure user authentication and authorization flows for backend
services with observability and testing."""

    result = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original,
    )

    assert result != original
    assert "auth" in result.lower()
    assert "access control" in result.lower()
    assert "backend" in result.lower()


@pytest.mark.asyncio
async def test_resume_enhancement_rejects_excessive_expansion(
    db_session: AsyncSession,
    test_user,
):
    """Тест что чрезмерное раздувание текста отклоняется."""

    class ExpandingClient(MockResumeClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {
                    "enhanced_text": (
                        "Built secure backend services with Python and FastAPI. "
                        "This solution was designed, architected, implemented, "
                        "documented, monitored, validated, optimized, and reviewed "
                        "for every possible operational scenario. "
                        "It includes extensive narrative about workflows, metrics, "
                        "stakeholders, delivery, collaboration, and future roadmap. "
                        "Built secure backend services with Python and FastAPI. "
                        "This solution was designed, architected, implemented, "
                        "documented, monitored, validated, optimized, and reviewed "
                        "for every possible operational scenario. "
                        "It includes extensive narrative about workflows, metrics, "
                        "stakeholders, delivery, collaboration, and future roadmap. "
                        "Built secure backend services with Python and FastAPI. "
                        "This solution was designed, architected, implemented, "
                        "documented, monitored, validated, optimized, and reviewed "
                        "for every possible operational scenario. "
                        "It includes extensive narrative about workflows, metrics, "
                        "stakeholders, delivery, collaboration, and future roadmap."
                    ),
                },
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=ExpandingClient())
    service = ResumeGenerationService()
    service.ai_orchestrator = orchestrator

    original = "Built secure backend services with Python and FastAPI."

    result = await service.enhance_resume_with_ai(
        session=db_session,
        user_id=test_user.id,
        resume_text=original,
    )

    assert result == original
    assert result.count("Python") == 1


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


def test_resume_generation_normalizes_and_filters_display_skills() -> None:
    service = ResumeGenerationService()

    selected = service._select_resume_skills(
        raw_skills=[
            "Technologies: Python",
            "HTML",
            "Mako",
            "Dockerfile",
            "devloher",
            "chatgpt",
            "llm",
            "ai",
            "AI tools: OpenAI",
            "Automation tools: Telegram Bot",
            "ai workflow",
        ],
        matched_keywords=["Python", "OpenAI", "AI workflow"],
    )

    assert selected == [
        "Python",
        "OpenAI",
        "AI Workflow",
        "developer",
        "ChatGPT",
        "LLM",
        "AI",
        "Telegram Bot",
    ]


def test_resume_rendered_text_does_not_include_internal_review_notes() -> None:
    rendered = render_resume(
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
        headline="Python, automation, devloher, Prompt Engineering, Data Science, Vibe-coding",
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
    assert "Python Automation & AI Workflow Engineer" in joined
    assert "devloher" not in joined
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
        achievements=[
            {
                "title": "Создание AI-платформы",
                "fact_status": "confirmed",
                "situation": "Нужно было ускорить запуск продукта",
                "task": "Спроектировать и внедрить backend для AI workflow",
                "action": "Собрал сервисы, API и pipeline интеграции",
                "result": "Сократил time-to-market на 20%",
                "metric_text": "time-to-market -20%",
            }
        ],
        keywords=["Python"],
    )

    assert selected == [
        {
            "title": "Создание AI-платформы",
            "fact_status": "confirmed",
            "reason": "ai_relevance",
            "situation": "Нужно было ускорить запуск продукта",
            "task": "Спроектировать и внедрить backend для AI workflow",
            "action": "Собрал сервисы, API и pipeline интеграции",
            "result": "Сократил time-to-market на 20%",
            "metric_text": "time-to-market -20%",
        }
    ]

    claims = service._build_claims_needing_confirmation(
        profile=SimpleNamespace(full_name="Test User"),
        selected_achievements=selected,
    )

    assert claims == []


def test_resume_can_projectize_selected_evidence_bank_item() -> None:
    service = ResumeGenerationService()

    selected = service._selected_achievements_from_evidence_bank(
        selected_evidence_ids=["evidence-1"],
        evidence_by_id={
            "evidence-1": {
                "id": "evidence-1",
                "title": "ИИ-система мониторинга безопасности",
                "snippet_text": "AI computer vision monitoring project from resume.",
                "source_type": "resume_structured",
                "skills": ["AI", "computer vision"],
                "fact_status": "user_provided",
                "star_summary": {"category": "ai_project"},
            }
        },
    )

    assert selected == [
        {
            "id": "evidence-1",
            "title": "ИИ-система мониторинга безопасности",
            "situation": None,
            "task": None,
            "action": "AI computer vision monitoring project from resume.",
            "result": None,
            "metric_text": None,
            "fact_status": "user_provided",
            "reason": "evidence_bank_project",
            "skills": ["AI", "computer vision"],
        }
    ]


def test_resume_balances_fallback_evidence_categories() -> None:
    service = ResumeGenerationService()

    ranked = [
        {"evidence_id": "eng-1", "title": "FastAPI backend", "score": 1.0},
        {"evidence_id": "eng-2", "title": "Repository architecture", "score": 0.95},
        {"evidence_id": "auto-1", "title": "OpenAI workflow", "score": 0.7},
        {"evidence_id": "auto-2", "title": "Telegram automation", "score": 0.65},
        {"evidence_id": "domain-1", "title": "Computer vision monitoring", "score": 0.5},
        {"evidence_id": "analytics-1", "title": "Analytics pipeline", "score": 0.4},
    ]
    evidence_by_id = {
        "eng-1": {
            "star_summary": {"category": "architecture_evidence"},
            "skills": ["FastAPI", "Backend Architecture"],
        },
        "eng-2": {
            "star_summary": {"category": "github_architecture"},
            "skills": ["Backend Architecture"],
        },
        "auto-1": {
            "star_summary": {"category": "automation_project"},
            "skills": ["OpenAI", "Workflow Orchestration"],
        },
        "auto-2": {
            "star_summary": {"category": "automation_project"},
            "skills": ["Telegram Bot", "Automation"],
        },
        "domain-1": {
            "star_summary": {"category": "computer_vision"},
            "skills": ["Computer Vision"],
        },
        "analytics-1": {
            "star_summary": {"category": "analytics_project"},
            "skills": ["Analytics"],
        },
    }

    selected = service._balance_ranked_evidence_selection(
        ranked_evidence=ranked,
        evidence_by_id=evidence_by_id,
        limit=5,
    )

    assert [item["evidence_id"] for item in selected] == [
        "eng-1",
        "eng-2",
        "auto-1",
        "auto-2",
        "domain-1",
    ]


def test_resume_competency_mapping_prefers_specific_evidence() -> None:
    service = ResumeGenerationService()

    evidence = service._find_best_evidence_for_competency(
        "Docker",
        [
            {
                "id": "workflow",
                "title": "AI workflow orchestration",
                "snippet_text": "OpenAI workflow automation pipeline.",
                "skills": ["AI Workflow", "OpenAI"],
            },
            {
                "id": "infra",
                "title": "Configured Docker-based local infrastructure",
                "snippet_text": "Docker Compose with Redis and PostgreSQL services.",
                "skills": ["Docker", "Infrastructure", "Redis", "PostgreSQL"],
            },
        ],
    )

    assert evidence["id"] == "infra"


def test_resume_competency_mapping_does_not_force_git_to_workflow_evidence() -> None:
    service = ResumeGenerationService()

    mapping = service._build_competency_mapping(
        relevant_to_vacancy=["Git"],
        evidence_snippets=[
            {
                "id": "workflow",
                "title": "AI workflow orchestration",
                "snippet_text": "OpenAI workflow automation pipeline.",
                "skills": ["AI Workflow", "OpenAI"],
                "fact_status": "user_provided",
            }
        ],
        missing_keywords=[],
    )

    assert mapping == [
        {
            "competency": "Git",
            "coverage": "profile_keyword",
            "evidence_id": None,
            "evidence_title": None,
            "evidence": (
                "Использование Git в проектной разработке требует отдельного подтверждения"
            ),
            "fact_status": "needs_review",
        }
    ]


def test_resume_competency_mapping_uses_git_only_with_repository_evidence() -> None:
    service = ResumeGenerationService()

    mapping = service._build_competency_mapping(
        relevant_to_vacancy=["Git"],
        evidence_snippets=[
            {
                "id": "repo",
                "title": "Repository architecture",
                "snippet_text": "GitHub repository with version control and structured commits.",
                "skills": ["Git", "GitHub"],
                "fact_status": "user_provided",
            }
        ],
        missing_keywords=[],
    )

    assert mapping[0]["coverage"] == "supported"
    assert mapping[0]["evidence_id"] == "repo"
    assert mapping[0]["evidence"] == "Использование Git/repository workflow в проектной разработке"


def test_resume_competency_mapping_does_not_map_generic_ai_to_prompt_orchestration() -> None:
    service = ResumeGenerationService()

    mapping = service._build_competency_mapping(
        relevant_to_vacancy=["Искусственный интеллект"],
        evidence_snippets=[
            {
                "id": "prompt",
                "title": "Prompt Engineering",
                "snippet_text": "Built ChatGPT prompts and AI-assisted workflows.",
                "skills": ["ChatGPT", "LLM", "prompt engineering", "automation"],
                "fact_status": "user_provided",
            }
        ],
        missing_keywords=[],
    )

    assert mapping[0]["coverage"] == "profile_keyword"
    assert mapping[0]["evidence_id"] is None
    assert mapping[0]["evidence"] == (
        "Практический опыт с искусственным интеллектом требует отдельного подтверждения"
    )


def test_resume_project_sections_ground_computer_vision_and_analytics() -> None:
    service = ResumeGenerationService()

    sections = service._build_project_sections(
        service._add_project_narratives(
            [
                {
                    "title": "ИИ-контроль качества по изображениям",
                    "action": "Computer vision monitoring for quality control.",
                    "skills": ["Computer Vision", "Monitoring", "Quality Control"],
                    "fact_status": "confirmed",
                },
                {
                    "title": "Analytics pipeline",
                    "action": "Built analytics pipeline for operational analysis.",
                    "skills": ["Analytics", "Data Analysis"],
                    "fact_status": "confirmed",
                },
            ]
        )
    )

    assert sections[0]["project"] == "AI Quality Monitoring"
    assert sections[0]["role"] == "AI / Computer Vision Project"
    assert any("мониторинга качества" in item for item in sections[0]["bullets"])
    assert sections[1]["project"] == "Analytics Pipeline"
    assert any("прикладных сигналов" in item for item in sections[1]["bullets"])


def test_resume_project_bullets_include_domain_impact_for_safety_monitoring() -> None:
    service = ResumeGenerationService()

    sections = service._build_project_sections(
        service._add_project_narratives(
            [
                {
                    "title": "AI monitoring system для пансионатов",
                    "action": (
                        "Computer vision monitoring for elderly safety in care homes."
                    ),
                    "skills": ["Computer Vision", "Monitoring", "Safety"],
                    "fact_status": "confirmed",
                }
            ]
        )
    )

    assert sections[0]["project"] == "AI Quality Monitoring"
    assert any(
        "мониторинга безопасности в пансионатах для пожилых" in item
        for item in sections[0]["bullets"]
    )


def test_resume_project_bullets_include_domain_impact_for_pvc_quality_control() -> None:
    service = ResumeGenerationService()

    sections = service._build_project_sections(
        service._add_project_narratives(
            [
                {
                    "title": "ИИ-контроль качества ПВХ изделий",
                    "action": "Computer vision analysis of images and video for PVC quality control.",
                    "skills": ["Computer Vision", "Quality Control"],
                    "fact_status": "confirmed",
                }
            ]
        )
    )

    assert any(
        item == "Автоматизировал анализ изображений и видео для контроля качества ПВХ изделий"
        for item in sections[0]["bullets"]
    )


def test_resume_adds_project_narratives_for_architecture_achievements() -> None:
    service = ResumeGenerationService()

    enriched = service._add_project_narratives(
        [
            {
                "title": "Разработка AI workflow orchestration системы",
                "action": "Implemented AI Workflow and OpenAI orchestration",
                "skills": ["AI Workflow", "OpenAI", "Workflow Orchestration"],
                "fact_status": "confirmed",
            },
            {
                "title": "Разработка FastAPI backend сервиса",
                "action": "Implemented FastAPI backend architecture",
                "skills": ["FastAPI", "Backend Architecture", "SQLAlchemy"],
                "fact_status": "confirmed",
            },
        ]
    )

    assert "tailored resume" in enriched[0]["narrative"]
    assert "application tracking" in enriched[1]["narrative"]


def test_resume_renderer_prints_project_narrative() -> None:
    rendered = render_resume(
        {
            "candidate": {"full_name": "Test User"},
            "target_vacancy": {"title": "AI Specialist"},
            "sections": {
                "summary_bullets": [],
                "skills": ["Python"],
                "experience": [],
                "selected_achievements": [
                    {
                        "title": "Разработка FastAPI backend сервиса",
                        "narrative": "API, persistence layer и document generation",
                    }
                ],
            },
        }
    )

    assert "Разработка FastAPI backend сервиса — API, persistence layer" in rendered


def test_resume_builds_structured_project_sections_from_achievements() -> None:
    service = ResumeGenerationService()

    achievements = service._add_project_narratives(
        [
            {
                "title": "Разработка AI workflow orchestration системы",
                "action": "Implemented AI Workflow, OpenAI orchestration and evidence review",
                "skills": ["AI Workflow", "OpenAI", "FastAPI", "PostgreSQL"],
                "fact_status": "confirmed",
                "reason": "evidence_bank_project",
            }
        ]
    )

    project_sections = service._build_project_sections(achievements)

    assert project_sections == [
        {
            "project": "AI Career Copilot",
            "role": "Backend / AI Workflow System",
            "bullets": [
                "Разработал workflow анализа вакансий и генерации tailored resume",
                "Интегрировал AI orchestration flow",
                (
                    "Спроектировал FastAPI backend для AI Career Copilot, "
                    "включающий pipeline анализа вакансий, генерацию tailored resume "
                    "и workflow review"
                ),
                "Спроектировал evidence-review architecture",
                "Спроектировал persistence layer для хранения прикладных данных",
            ],
        }
    ]


def test_resume_renderer_prints_structured_project_sections() -> None:
    rendered = render_resume(
        {
            "candidate": {"full_name": "Test User"},
            "target_vacancy": {"title": "AI Specialist"},
            "sections": {
                "summary_bullets": [],
                "skills": ["Python"],
                "experience": [],
                "project_sections": [
                    {
                        "project": "AI Career Copilot",
                        "role": "Backend / AI Workflow System",
                        "bullets": [
                            "Разработал workflow анализа вакансий и генерации tailored resume",
                            (
                                "Спроектировал FastAPI backend для AI Career Copilot, "
                                "включающий pipeline анализа вакансий, генерацию tailored resume "
                                "и workflow review"
                            ),
                        ],
                    }
                ],
                "selected_achievements": [
                    {
                        "title": "Flat fallback should not render",
                        "narrative": "Hidden when structured project sections exist",
                    }
                ],
            },
        }
    )

    assert "AI Career Copilot" in rendered
    assert "Backend / AI Workflow System" in rendered
    assert "- Разработал workflow анализа вакансий" in rendered
    assert "- Спроектировал FastAPI backend для AI Career Copilot" in rendered
    assert "Flat fallback should not render" not in rendered


def test_resume_builds_ats_tailored_summary_and_competency_mapping() -> None:
    service = ResumeGenerationService()

    tailoring = service._build_ats_tailoring_sections(
        vacancy_title="AI Automation Specialist",
        matched_keywords=["Prompt Engineering", "LLM", "Automation", "Python"],
        missing_keywords=["Kubernetes"],
        selected_skills=["ChatGPT", "AI workflow"],
        selected_achievements=[
            {
                "title": "ИИ-система мониторинга безопасности",
                "fact_status": "user_provided",
            }
        ],
        evidence_snippets=[
            {
                "id": "e1",
                "title": "Prompt Engineering",
                "snippet_text": "Built ChatGPT prompts and AI-assisted workflows.",
                "skills": ["ChatGPT", "LLM", "prompt engineering", "automation"],
                "fact_status": "user_provided",
            },
            {
                "id": "e2",
                "title": "Python AI system",
                "snippet_text": "Python-based AI monitoring system.",
                "skills": ["Python", "AI"],
                "fact_status": "user_provided",
            },
        ],
    )

    summary = tailoring["vacancy_aligned_summary"]
    assert summary.startswith("Python-разработчик и AI automation engineer")
    assert "Кандидат на позицию" not in summary
    assert "Workflow automation" in tailoring["relevant_to_vacancy"]
    assert "Python-based AI systems" in tailoring["relevant_to_vacancy"]
    assert any(
        item["competency"] == "Prompt engineering"
        and item["evidence"]
        == "Проектирование prompt/workflow orchestration для AI-assisted resume tailoring"
        for item in tailoring["competency_mapping"]
    )
    assert any(
        item["competency"] == "Workflow automation"
        and item["evidence"]
        == "Разработка AI workflow pipeline для анализа вакансий и генерации документов"
        for item in tailoring["competency_mapping"]
    )
    assert all(
        item.get("evidence") != "Technology stack from resume"
        for item in tailoring["competency_mapping"]
    )
