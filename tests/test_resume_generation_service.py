from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import AIOrchestrator
from app.ai.clients.base import BaseLLMClient
from app.domain.text_normalization import dedupe_subsumed_phrases
from app.services.evidence_bank_service import EvidenceBankItem, EvidenceBankService
from app.services.profile_structuring_service import ProfileStructuringService
from app.services.resume_generation_service import ResumeGenerationService
from app.services.resume_renderer import render_resume
from app.services.text_polish.narrative_builder import NarrativeBuilder


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


def test_resume_generation_extracts_capability_skills_from_experience() -> None:
    service = ResumeGenerationService()

    capability_skills = service._extract_capability_skills_from_experience(
        [
            {
                "description_raw": (
                    "Управление отделом снабжения\n"
                    "Планирование бюджета снабжения\n"
                    "Контроль логистических процессов\n"
                    "Контроль поставок\n"
                    "Ведение переговоров с поставщиками\n"
                    "Контроль исполнения договорных обязательств\n"
                    "Управление складскими запасами\n"
                    "Претензионная работа"
                )
            }
        ]
    )

    assert capability_skills == [
        "Закупочная деятельность",
        "Управление складскими запасами",
        "Бюджетирование",
        "Договорная работа",
        "Ведение переговоров",
        "Управление поставщиками",
        "Контроль поставок",
        "Претензионная работа",
        "Логистика",
    ]


def test_extract_capability_skills_from_experience_uses_responsibility_items() -> None:
    service = ResumeGenerationService()

    result = service._extract_capability_skills_from_experience(
        experience_items=[
            {
                "role": "Заместитель директора по МТО",
                "responsibilities": [
                    "Организация закупочной деятельности",
                    "Планирование бюджета снабжения",
                    "Ведение переговоров с поставщиками",
                    "Контроль исполнения договоров",
                ],
            }
        ]
    )

    assert "Закупочная деятельность" in result
    assert "Материально-техническое обеспечение" in result
    assert "Бюджетирование" in result
    assert "Ведение переговоров" in result
    assert "Договорная работа" in result


def test_resume_skills_include_business_capabilities_from_experience() -> None:
    service = ResumeGenerationService()

    experience_items = [
        {
            "description_raw": (
                "Организация закупочной деятельности\n"
                "Материально-техническое обеспечение\n"
                "Управление складскими запасами\n"
                "Бюджетирование\n"
                "Договорная работа\n"
                "Ведение переговоров\n"
                "Управление поставщиками\n"
                "Контроль поставок\n"
                "Претензионная работа\n"
                "Логистика"
            )
        }
    ]

    capability_skills = service._extract_capability_skills_from_experience(
        experience_items,
    )
    selected_skills = service._select_resume_skills(
        raw_skills=[*capability_skills, "Excel", "1С ERP", "Складская логистика"],
        matched_keywords=["Excel", "1С ERP", "Складская логистика"],
    )

    assert capability_skills == [
        "Закупочная деятельность",
        "Материально-техническое обеспечение",
        "Управление складскими запасами",
        "Бюджетирование",
        "Договорная работа",
        "Ведение переговоров",
        "Управление поставщиками",
        "Контроль поставок",
        "Претензионная работа",
        "Логистика",
    ]
    assert selected_skills == [
        "Закупочная деятельность",
        "Материально-техническое обеспечение",
        "Управление складскими запасами",
        "Бюджетирование",
        "Договорная работа",
        "Ведение переговоров",
        "Управление поставщиками",
        "Контроль поставок",
        "Претензионная работа",
        "Складская логистика",
    ]


def test_rendered_resume_skills_include_experience_derived_business_capabilities() -> None:
    service = ResumeGenerationService()
    profile = SimpleNamespace(
        experiences=[
            SimpleNamespace(
                company="ООО МТК",
                role="Заместитель начальника отдела снабжения",
                start_date=date(2015, 1, 1),
                end_date=date(2024, 1, 1),
                description_raw=(
                    "Организация закупочной деятельности\n"
                    "Планирование бюджета снабжения\n"
                    "Контроль поставок\n"
                    "Ведение переговоров с поставщиками\n"
                    "Контроль исполнения договорных обязательств\n"
                    "Управление складскими запасами"
                ),
            )
        ]
    )

    experience_items = service._build_experience_items(profile)
    raw_skills = service._dedupe_preserve_order(
        [
            *service._extract_capability_skills_from_experience(experience_items),
            "Excel",
            "Складская логистика",
            "1С",
        ]
    )
    selected_skills = service._select_resume_skills(
        raw_skills=raw_skills,
        matched_keywords=["Excel", "Складская логистика", "1С"],
    )
    rendered = render_resume(
        {
            "candidate": {"full_name": "Тестовый кандидат"},
            "target_vacancy": {"title": "Заместитель начальника отдела снабжения"},
            "sections": {
                "vacancy_aligned_summary": (
                    "Руководитель в сфере материально-технического обеспечения "
                    "с опытом закупок, бюджетирования и договорной работы."
                ),
                "skills": selected_skills,
                "experience": experience_items,
                "education": [],
                "courses": [],
                "internships": [],
                "project_sections": [],
                "selected_achievements": [],
            },
        }
    )

    assert "- Закупочная деятельность" in rendered
    assert "- Управление складскими запасами" in rendered
    assert "- Бюджетирование" in rendered
    assert "- Договорная работа" in rendered
    assert "- Ведение переговоров" in rendered
    assert rendered.index("- Закупочная деятельность") < rendered.index("- Excel")
    assert "- Отвечал за организацию закупочной деятельности и управление поставщиками." in rendered
    assert "- Контролировал бюджет снабжения, складские запасы и логистические процессы." in rendered
    assert (
        "- Руководил работой отдела снабжения и обеспечивал исполнение договорных обязательств."
        in rendered
    )
    assert "- Организация закупочной деятельности" not in rendered


def test_resume_generation_prioritizes_capability_skills_before_tools() -> None:
    service = ResumeGenerationService()

    selected = service._select_resume_skills(
        raw_skills=[
            "Закупочная деятельность",
            "Материально-техническое обеспечение",
            "Управление складскими запасами",
            "Бюджетирование",
            "Договорная работа",
            "Ведение переговоров",
            "Управление поставщиками",
            "Контроль поставок",
            "Претензионная работа",
            "Логистика",
            "Excel",
            "1с erp",
            "Складская логистика",
        ],
        matched_keywords=["Excel", "1С ERP", "Складская логистика"],
    )

    assert selected[:10] == [
        "Закупочная деятельность",
        "Материально-техническое обеспечение",
        "Управление складскими запасами",
        "Бюджетирование",
        "Договорная работа",
        "Ведение переговоров",
        "Управление поставщиками",
        "Контроль поставок",
        "Претензионная работа",
        "Складская логистика",
    ]
    assert selected == [
        "Закупочная деятельность",
        "Материально-техническое обеспечение",
        "Управление складскими запасами",
        "Бюджетирование",
        "Договорная работа",
        "Ведение переговоров",
        "Управление поставщиками",
        "Контроль поставок",
        "Претензионная работа",
        "Складская логистика",
    ]


def test_resume_generation_preserves_designer_tool_skills_and_summary_domain() -> None:
    service = ResumeGenerationService()

    raw_skills = service._split_skill_text(
        """
Adobe Photoshop
Adobe Illustrator
Figma
CorelDRAW
Полиграфический дизайн
Брендинг
Подготовка макетов к печати
Визуальная коммуникация
Типографика
"""
    )
    selected_skills = service._select_resume_skills(
        raw_skills=raw_skills,
        matched_keywords=[
            "Adobe Photoshop",
            "CorelDRAW",
            "подготовка макетов к печати",
        ],
    )
    summary = service._build_vacancy_aligned_summary(
        vacancy_title="Графический дизайнер",
        selected_skills=selected_skills,
        selected_achievements=[
            {"title": "Сократила сроки подготовки макетов на 30%"},
        ],
        experience_items=[
            {
                "period": "01.2018 - 01.2024",
                "description_raw": (
                    "Разработка рекламных материалов\n"
                    "Создание фирменного стиля\n"
                    "Подготовка макетов к печати"
                ),
            }
        ],
        top_alignment_evidence=[
            {
                "summary_phrase": "сроки подготовки макетов на 30%",
                "confidence": "high",
            }
        ],
    )

    assert selected_skills[:6] == [
        "Adobe Photoshop",
        "Adobe Illustrator",
        "Figma",
        "CorelDRAW",
        "Полиграфический дизайн",
        "Брендинг",
    ]
    assert summary.startswith(
        "Графический дизайнер с опытом более 5 лет в "
        "графического дизайна, подготовки макетов к печати "
        "и работы с графическими редакторами."
    )
    assert "в сфере сроки подготовки макетов" not in summary


def test_resume_generation_splits_designer_experience_boundaries() -> None:
    service = ResumeGenerationService()

    normalized = service._normalize_experience_description(
        "Разработка рекламных материалов Создание фирменного стиля "
        "Разработка визуальных концепций Создание контента для социальных сетей"
    )

    assert normalized == (
        "Разработка рекламных материалов\n"
        "Создание фирменного стиля\n"
        "Разработка визуальных концепций\n"
        "Создание контента для социальных сетей"
    )


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
                    "Опыт, релевантный позиции Backend Developer: Python."
                ],
                "vacancy_fit_narrative": {
                    "matched_strengths": [{"label": "Python"}],
                    "transferable_strengths": [{"label": "ведение документации"}],
                    "critical_gaps": [{"label": "Redis"}],
                },
                "relevant_to_vacancy": ["Python"],
                "competency_mapping": [
                    {"competency": "Python", "evidence": "Python project"}
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
    assert "КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ" in rendered
    assert "Создание ИИ-системы для мониторинга безопасности" in rendered

    assert "SUMMARY" not in rendered
    assert "SKILLS" not in rendered
    assert "EXPERIENCE" not in rendered
    assert "REVIEW NOTES" not in rendered
    assert "FIT SUMMARY" not in rendered
    assert "Match score" not in rendered
    assert "missing or weakly represented" not in rendered
    assert "needs_confirmation" not in rendered
    assert "ПОЧЕМУ ВЫ ПОДХОДИТЕ" not in rendered
    assert "РЕЛЕВАНТНО ДЛЯ ВАКАНСИИ" not in rendered
    assert "КАРТА КОМПЕТЕНЦИЙ" not in rendered
    assert "Переносимые компетенции" not in rendered
    assert "Требуют подтверждения" not in rendered


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
        top_alignment_evidence=[
            {"summary_phrase": "ведение проектной документации"},
            {"summary_phrase": "коммерческие проекты"},
        ],
        vacancy_aligned_summary="Внедрял процессы и координировал проекты.",
    )

    joined = "\n".join(bullets)

    assert "Профессиональный фокус" in joined
    assert "Python Automation & AI Workflow Engineer" not in joined
    assert "devloher" not in joined
    assert "Ключевой профиль опыта" in joined
    assert "ведение проектной документации" in joined
    assert "коммерческие проекты" in joined
    assert "Опыт, релевантный позиции" not in joined
    assert "Дополнительные навыки" not in joined
    assert "Профессиональный результат для отклика" in joined
    assert "Подтверждённые пересечения" not in joined
    assert "Подтверждённый профессиональный опыт" not in joined

    assert "Candidate profile aligned" not in joined
    assert "Profile-confirmed" not in joined
    assert "Broader skill base" not in joined
    assert "Relevant project experience" not in joined
    assert "Recent role" not in joined


def test_summary_bullets_prefer_top_alignment_evidence() -> None:
    service = ResumeGenerationService()

    profile = SimpleNamespace(
        headline="Project Manager",
    )

    bullets = service._build_summary_bullets(
        profile=profile,
        vacancy_title="Руководитель проектов",
        selected_skills=["Agile", "Jira"],
        selected_achievements=[
            {
                "title": "Запустила 8 проектов в срок",
                "fact_status": "confirmed",
                "reason": "confirmed_profile",
            }
        ],
        matched_keywords=["Agile", "Jira"],
        top_alignment_evidence=[
            {"summary_phrase": "ведение проектной документации"},
            {"summary_phrase": "управление коммерческими проектами"},
        ],
        vacancy_aligned_summary="fallback summary",
    )

    joined = " ".join(bullets).lower()

    assert "ведение проектной документации" in joined
    assert "управление коммерческими проектами" in joined
    assert "fallback summary" not in joined


def test_normalize_profile_focus_does_not_invent_ai_role_label() -> None:
    service = ResumeGenerationService()

    focus = service._normalize_profile_focus("Python, automation, prompt engineering, LLM")

    assert focus != "Python Automation & AI Workflow Engineer"
    assert focus != "AI Automation Engineer / Prompt Engineer"
    assert "Python" in focus
    assert "LLM" in focus


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


def test_resume_skill_cleanup_splits_known_multiword_skills() -> None:
    service = ResumeGenerationService()

    skills = service._split_skill_text(
        "Гражданское право Договорное право Legal Research Документооборот Арбитраж"
    )

    assert skills == [
        "Гражданское право",
        "Договорное право",
        "Legal Research",
        "Документооборот",
        "Арбитраж",
    ]


def test_resume_generation_warnings_are_russian() -> None:
    service = ResumeGenerationService()

    warnings = service._build_warnings(
        profile=SimpleNamespace(),
        selected_achievements=[],
        analysis_match_score=27,
        missing_keywords=["FastAPI"],
    )

    messages = [item.message for item in warnings]

    assert any(
        "Оценка соответствия вакансии сейчас низкая" in message
        for message in messages
    )
    assert any(
        "Ключевые слова вакансии представлены слабо или отсутствуют" in message
        for message in messages
    )
    assert any(
        "Черновик резюме подготовлен в ATS-совместимом текстовом виде" in message
        for message in messages
    )


def test_resume_skills_prefer_profile_summary_over_raw_text_section() -> None:
    service = ResumeGenerationService()

    skills = service._extract_skills_from_profile_or_raw_text(
        profile_summary="Python, LLM, Docker",
        raw_text="""
Иван Иванов
Юрист

НАВЫКИ: Гражданское право Договорное право Арбитраж Документооборот
""",
    )

    assert skills == ["Python", "LLM", "Docker"]
    assert "Гражданское право" not in skills


def test_resume_filters_low_confidence_experience_from_noisy_layout() -> None:
    service = ResumeGenerationService()

    assert service._looks_like_low_confidence_experience_item(
        {
            "company": "(ООО «СГЦ ОПЕКА») 2. Автоматизированный Алтайский Государственный Медицинский ИИ-контроль качества Университет",
            "role": "электромонтер по ремонту и ПВХ оконных изделий обслуживанию электрооборудования по изображениям и",
            "description_raw": "video layout noise",
        }
    )


def test_resume_keeps_honest_non_it_work_experience() -> None:
    service = ResumeGenerationService()

    profile = SimpleNamespace(
        experiences=[
            SimpleNamespace(
                company="Алтайский Государственный Медицинский Университет",
                role="электромонтер по ремонту и обслуживанию электрооборудования",
                start_date=date(2015, 1, 1),
                end_date=None,
                description_raw=(
                    "Алтайский Государственный Медицинский Университет, "
                    "электромонтер по ремонту и обслуживанию электрооборудования"
                ),
            )
        ]
    )

    items = service._build_experience_items(profile)

    assert items == [
        {
            "company": "Алтайский Государственный Медицинский Университет",
            "role": "электромонтер по ремонту и обслуживанию электрооборудования",
            "period": "01.2015 - н.в.",
            "description_raw": (
                "Алтайский Государственный Медицинский Университет, "
                "электромонтер по ремонту и обслуживанию электрооборудования"
            ),
        }
    ]


def test_resume_experience_fallback_keeps_items_when_filter_removes_all() -> None:
    service = ResumeGenerationService()
    profile = SimpleNamespace(
        experiences=[
            SimpleNamespace(
                company="ООО МТК",
                role="Заместитель начальника отдела снабжения",
                start_date=date(2015, 1, 1),
                end_date=date(2024, 1, 1),
                description_raw=(
                    "Управление отделом снабжения\n"
                    "Ведение переговоров с поставщиками\n"
                    "Контроль исполнения договорных обязательств"
                ),
            )
        ]
    )

    service._looks_like_low_confidence_experience_item = lambda item: True  # type: ignore[method-assign]

    items = service._build_experience_items(profile)

    assert len(items) == 1
    assert items[0]["role"] == "Заместитель начальника отдела снабжения"
    assert items[0]["company"] == "ООО МТК"



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
        selected_achievements=[],
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
        selected_achievements=[],
    )

    assert mapping[0]["coverage"] == "supported"
    assert mapping[0]["evidence_id"] == "repo"
    assert mapping[0]["evidence"] == "Использование Git/repository workflow в проектной разработке"


def test_resume_competency_mapping_skips_evidence_not_backed_by_selected_achievement() -> None:
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
        selected_achievements=[
            {
                "title": "Some other achievement",
            }
        ],
    )

    assert mapping == []


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
        selected_achievements=[],
    )

    assert mapping[0]["coverage"] == "profile_keyword"
    assert mapping[0]["evidence_id"] is None
    assert mapping[0]["evidence"] == (
        "Практический опыт с искусственным интеллектом требует отдельного подтверждения"
    )


def test_relevant_to_vacancy_does_not_infer_ai_tooling_from_plain_ai_noise() -> None:
    service = ResumeGenerationService()

    relevant = service._build_relevant_to_vacancy(
        matched_keywords=[],
        selected_skills=[],
        evidence_snippets=[
            {
                "title": "Technology stack from resume",
                "skills": ["AI", "Терапия", "Клиническая диагностика"],
                "snippet_text": "AI, Терапия, Клиническая диагностика",
            }
        ],
    )

    assert "AI/LLM tooling" not in relevant


def test_plumber_experience_humanizer_does_not_infer_supply_from_water_supply() -> None:
    service = ResumeGenerationService()

    result = service._humanize_supply_experience_description(
        (
            "Монтаж систем водоснабжения и канализации\n"
            "Обслуживание сантехнического оборудования\n"
            "Замена трубопроводов\n"
            "Устранение аварийных ситуаций"
        )
    )

    lowered = result.lower()
    assert "закуп" not in lowered
    assert "снабжения" not in lowered.replace("водоснабжения", "")
    assert "водоснабжения" in lowered


def test_plumber_skills_do_not_gain_procurement_from_water_supply() -> None:
    service = ResumeGenerationService()

    selected = service._select_resume_skills(
        raw_skills=["Монтаж систем водоснабжения", "Ремонт трубопроводов"],
        matched_keywords=["Монтаж систем водоснабжения"],
    )

    assert "Закупочная деятельность" not in selected


def test_resume_project_sections_ground_computer_vision_and_analytics() -> None:
    narrative_builder = NarrativeBuilder()

    sections = narrative_builder.build_project_sections(
        narrative_builder.add_project_narratives(
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

    assert sections[0]["project"] == "ИИ-контроль качества по изображениям"
    assert sections[0]["role"] == "Visual Data Processing Evidence"
    assert any("обработку изображений и видео" in item for item in sections[0]["bullets"])
    assert sections[1]["project"] == "Analytics pipeline"
    assert any("прикладных сигналов" in item for item in sections[1]["bullets"])


def test_resume_project_bullets_include_generic_impact_for_safety_monitoring() -> None:
    narrative_builder = NarrativeBuilder()

    sections = narrative_builder.build_project_sections(
        narrative_builder.add_project_narratives(
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

    assert sections[0]["project"] == "AI monitoring system для пансионатов"
    assert any(
        "обработку изображений и видео" in item
        and "мониторинга" in item
        for item in sections[0]["bullets"]
    )


def test_resume_project_bullets_include_generic_impact_for_pvc_quality_control() -> None:
    narrative_builder = NarrativeBuilder()

    sections = narrative_builder.build_project_sections(
        narrative_builder.add_project_narratives(
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
        "обработку изображений и видео" in item
        for item in sections[0]["bullets"]
    )


def test_resume_does_not_invent_architecture_narratives_from_technical_keywords() -> None:
    narrative_builder = NarrativeBuilder()

    enriched = narrative_builder.add_project_narratives(
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

    joined = "\n".join(str(item.get("narrative") or "") for item in enriched)

    assert "tailored resume" not in joined
    assert "application tracking" not in joined
    assert "pipeline анализа вакансий" not in joined


def test_resume_renderer_prints_project_narrative() -> None:
    rendered = render_resume(
        {
            "candidate": {"full_name": "Test User"},
            "target_vacancy": {"title": "AI Specialist"},
            "sections": {
                "summary_bullets": [],
                "skills": ["Python"],
                "experience": [
                    {
                        "company": "Алтайский Государственный Медицинский Университет",
                        "role": "электромонтер по ремонту и обслуживанию электрооборудования",
                        "period": "01.2015 - н.в.",
                        "description_raw": "non-IT operational experience",
                    }
                ],
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
    narrative_builder = NarrativeBuilder()

    achievements = narrative_builder.add_project_narratives(
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

    project_sections = narrative_builder.build_project_sections(achievements)

    assert project_sections == [
        {
            "project": "Разработка AI workflow orchestration системы",
            "role": "Workflow Implementation Evidence",
            "bullets": [
                "Зафиксированы workflow/orchestration implementation signals",
                "Зафиксированы backend/API implementation signals",
                "Зафиксированы evidence-review implementation signals",
                "Зафиксированы persistence-layer implementation signals",
            ],
        }
    ]


def test_resume_blocks_unconfirmed_low_ownership_evidence_from_strong_project_claims() -> None:
    narrative_builder = NarrativeBuilder()

    project_sections = narrative_builder.build_project_sections(
        [
            {
                "title": "Repository evidence: backend-related implementation signals",
                "action": (
                    "Repository evidence indicates backend-related implementation "
                    "signals. Candidate ownership is unknown."
                ),
                "skills": ["FastAPI", "PostgreSQL", "Docker"],
                "fact_status": "needs_confirmation",
                "candidate_ownership_confidence": "low",
                "requires_confirmation": True,
                "source_evidence_ids": ["ev-fastapi", "ev-db"],
            }
        ]
    )

    assert project_sections == []


def test_resume_renderer_prints_structured_project_sections() -> None:
    rendered = render_resume(
        {
            "candidate": {"full_name": "Test User"},
            "target_vacancy": {"title": "AI Specialist"},
            "sections": {
                "summary_bullets": [],
                "skills": ["Python"],
                "experience": [
                    {
                        "company": "Алтайский Государственный Медицинский Университет",
                        "role": "электромонтер по ремонту и обслуживанию электрооборудования",
                        "period": "01.2015 - н.в.",
                        "description_raw": "non-IT operational experience",
                    }
                ],
                "project_sections": [
                    {
                        "project": "Repository Evidence",
                        "role": "Project Evidence",
                        "bullets": [
                            "Зафиксированы workflow/orchestration implementation signals",
                            "Зафиксированы backend/API implementation signals",
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

    assert "Repository Evidence" in rendered
    assert "Project Evidence" in rendered
    assert "- Зафиксированы workflow/orchestration implementation signals" in rendered
    assert "- Зафиксированы backend/API implementation signals" in rendered
    assert "AI Career Copilot" not in rendered
    assert "tailored resume" not in rendered
    assert "Спроектировал FastAPI backend" not in rendered
    assert "Flat fallback should not render" not in rendered


def test_profile_structuring_extracts_education_without_internships() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
ОБРАЗОВАНИЕ
Алтайский государственный университет
Высшее образование
Специальность: Программное обеспечение вычислительной техники
СТАЖИРОВКИ
Prompt Engineering internship
"""
    )

    assert len(draft.education) == 1
    assert draft.education[0].institution == "Алтайский государственный университет"
    assert draft.education[0].specialty == "Программное обеспечение вычислительной техники"
    assert "СТАЖИРОВКИ" not in (draft.education[0].details or "")
    assert "internship" not in (draft.education[0].details or "").lower()


def test_resume_generation_builds_education_from_latest_extraction() -> None:
    service = ResumeGenerationService()

    education = service._build_education_items(
        profile=SimpleNamespace(),
        latest_extraction_text="""
ОБРАЗОВАНИЕ
Алтайский государственный университет
Высшее образование
Специальность: Программное обеспечение вычислительной техники
СТАЖИРОВКИ
Prompt Engineering internship
""",
    )

    assert education == []


def test_resume_generation_splits_education_and_courses_from_noisy_layout() -> None:
    service = ResumeGenerationService()
    extraction_text = """
ОБРАЗОВАНИЕ
прогнозирования университет имени И.И. Ползунова, Барнаул развития городской среды и оценки / Политехнический Университет)» Рязанское высшее воздушно-десантное командное училище им. В.Ф. Маргелова, Рязань / Data Science, нейронные сети, машинное обучение и искусственный интеллект университет искусственного интеллекта 2022 Программист на Python с нуля с помощью ChatGPT университет зерокодинга 2023 Аналитик данных с нуля с помощью ChatGPT университет зерокодинга 2024 Промпт-инжиниринг университет зерокодинга 2025
ПРОЕКТЫ
ИИ-система мониторинга безопасности
"""

    education = service._build_education_items(
        profile=SimpleNamespace(),
        latest_extraction_text=extraction_text,
    )
    courses = service._build_course_items(extraction_text)

    assert education == [
        {
            "details": (
                "Алтайский государственный технический университет "
                "им. И.И. Ползунова, Барнаул"
            )
        },
        {
            "details": (
                "Рязанское высшее воздушно-десантное командное училище "
                "им. В.Ф. Маргелова, Рязань"
            )
        }
    ]
    assert courses == [
        {
            "provider": None,
            "year": None,
            "title": (
                "Университет искусственного интеллекта, 2022 — "
                "Data Science, нейронные сети, машинное обучение и "
                "искусственный интеллект"
            ),
            "details": (
                "Университет искусственного интеллекта, 2022 — "
                "Data Science, нейронные сети, машинное обучение и "
                "искусственный интеллект"
            ),
        },
        {
            "provider": None,
            "year": None,
            "title": "Университет Зерокодинга, 2023 — Программист на Python с нуля с помощью ChatGPT",
            "details": (
                "Университет Зерокодинга, 2023 — "
                "Программист на Python с нуля с помощью ChatGPT"
            ),
        },
        {
            "provider": None,
            "year": None,
            "title": "Университет Зерокодинга, 2024 — Аналитик данных с нуля с помощью ChatGPT",
            "details": (
                "Университет Зерокодинга, 2024 — "
                "Аналитик данных с нуля с помощью ChatGPT"
            ),
        },
        {
            "provider": None,
            "year": None,
            "title": "Университет Зерокодинга, 2025 — Промпт-инжиниринг",
            "details": "Университет Зерокодинга, 2025 — Промпт-инжиниринг",
        },
    ]
    assert all("прогнозирования" not in item["details"] for item in education)
    assert all(len(item["details"]) <= 180 for item in education)


def test_resume_generation_handles_real_split_resume_education_layout() -> None:
    service = ResumeGenerationService()
    extraction_text = """
ОБРАЗОВАНИЕ                                                    отзывов населения
социальных объектах инфраструктуры для Алтайский государственный технический
прогнозирования университет имени И.И. Ползунова, Барнаул развития городской среды и оценки
инженер, Автомобиле- и тракторостроение устойчивого развития 1999 - 2001 территорий
Политехнический Университет)» Рязанское высшее воздушно-десантное командное училище им. В.Ф. Маргелова, Рязань
инженерный, командная тактическая воздушно-десантных войск 1993 - 1997
Курсы
Data Science, нейронные сети, машинное обучение и
искусственный интеллект
университет искусственного интеллекта
2022
Программист на Python с нуля с помощью ChatGPT
университет зерокодинга
2023
Аналитик данных с нуля с помощью ChatGPT
университет зерокодинга
2024
Промпт-инжиниринг
университет зерокодинга
2025
"""

    education = service._build_education_items(
        profile=SimpleNamespace(),
        latest_extraction_text=extraction_text,
    )
    courses = service._build_course_items(extraction_text)

    assert education == [
        {
            "details": (
                "Алтайский государственный технический университет "
                "им. И.И. Ползунова, Барнаул"
            )
        },
        {
            "details": (
                "Рязанское высшее воздушно-десантное командное училище "
                "им. В.Ф. Маргелова, Рязань"
            )
        },
    ]
    assert [item["details"] for item in courses] == [
        (
            "Университет искусственного интеллекта, 2022 — "
            "Data Science, нейронные сети, машинное обучение и "
            "искусственный интеллект"
        ),
        (
            "Университет Зерокодинга, 2023 — "
            "Программист на Python с нуля с помощью ChatGPT"
        ),
        (
            "Университет Зерокодинга, 2024 — "
            "Аналитик данных с нуля с помощью ChatGPT"
        ),
        "Университет Зерокодинга, 2025 — Промпт-инжиниринг",
    ]
    assert all("зерокод" not in item["details"].lower() for item in education)
    assert all("прогнозирования" not in item["details"] for item in education)


def test_resume_generation_extracts_courses_from_generic_title_provider_year_layout() -> None:
    service = ResumeGenerationService()

    courses = service._build_course_items(
        """
КУРСЫ
Python для анализа данных
Stepik
2021
Backend-разработка на FastAPI
OTUS
2024
"""
    )

    assert courses == [
        {
            "provider": None,
            "year": None,
            "title": "Stepik, 2021 — Python для анализа данных",
            "details": "Stepik, 2021 — Python для анализа данных",
        },
        {
            "provider": None,
            "year": None,
            "title": "OTUS, 2024 — Backend-разработка на FastAPI",
            "details": "OTUS, 2024 — Backend-разработка на FastAPI",
        },
    ]


def test_resume_generation_legacy_education_course_recovery_can_be_disabled() -> None:
    service = ResumeGenerationService(enable_legacy_recovery=False)

    assert service.legacy_recovery_service.recover_known_formal_education_lines(
        "Алтайский государственный технический университет имени И.И. Ползунова, Барнаул"
    ) == []

    assert service._extract_course_details(
        "Курсы Python с нуля Университет Зерокодинга 2024"
    ) == []


def test_resume_generation_legacy_mixed_layout_noise_can_be_disabled() -> None:
    service = ResumeGenerationService(enable_legacy_recovery=False)

    assert service._looks_like_mixed_layout_noise(
        "прогнозирования развития городской среды и ПВХ"
    ) is False


def test_resume_generation_low_confidence_experience_noise_can_be_disabled() -> None:
    service = ResumeGenerationService(enable_legacy_recovery=False)

    assert service._looks_like_low_confidence_experience_item(
        {
            "company": "",
            "role": "ИИ-контроль качества ПВХ оконных изделий",
            "description_raw": "по изображениям",
        }
    ) is False


def test_computer_vision_bullet_generation_is_domain_neutral() -> None:
    narrative_builder = NarrativeBuilder()

    bullet = narrative_builder.computer_vision_impact_bullet(
        "computer vision monitoring pipeline for image analysis"
    )

    assert "пвх" not in bullet.lower()
    assert "пансионат" not in bullet.lower()
    assert "пожил" not in bullet.lower()

    assert "изображений" in bullet.lower() or "visual" in bullet.lower()


def test_project_bullet_generation_does_not_invent_private_domain_identity() -> None:
    narrative_builder = NarrativeBuilder()

    bullets = narrative_builder.project_bullets_from_achievement(
        {
            "title": "Computer vision workflow",
            "skills": ["computer vision", "python"],
        }
    )

    joined = " ".join(bullets).lower()

    assert "пвх" not in joined
    assert "пансионат" not in joined
    assert "пожил" not in joined


def test_project_bullets_do_not_invent_ownership_from_technical_signals() -> None:
    narrative_builder = NarrativeBuilder()

    bullets = narrative_builder.project_bullets_from_achievement(
        {
            "title": "Repository architecture evidence",
            "skills": ["postgresql", "sqlalchemy", "docker", "redis"],
            "fact_status": "needs_confirmation",
            "ownership_confidence": "low",
            "requires_confirmation": True,
        }
    )

    joined = " ".join(bullets).lower()

    assert "спроектировал" not in joined
    assert "настроил" not in joined
    assert "implementation signals" in joined


def test_project_name_prefers_evidence_title_over_domain_template() -> None:
    narrative_builder = NarrativeBuilder()

    name = narrative_builder.project_name_from_achievement(
        {
            "title": "Repository evidence: document review workflow",
            "narrative": "career copilot tailored resume evidence review application tracking",
        }
    )

    assert name == "Repository evidence: document review workflow"
    assert name != "AI Quality Monitoring"
    assert name != "Content Factory"


def test_project_name_does_not_invent_private_product_identity_without_title() -> None:
    narrative_builder = NarrativeBuilder()

    name = narrative_builder.project_name_from_achievement(
        {
            "narrative": "career copilot tailored resume evidence review application tracking",
            "skills": ["fastapi", "postgresql"],
        }
    )

    assert name == "Backend Implementation Project"
    assert "Career Copilot" not in name
    assert "tailored resume" not in name.lower()


def test_project_role_is_evidence_label_not_invented_role_identity() -> None:
    narrative_builder = NarrativeBuilder()

    role = narrative_builder.project_role_from_achievement(
        {
            "title": "Repository evidence",
            "skills": ["computer vision", "python"],
            "fact_status": "needs_confirmation",
            "ownership_confidence": "low",
            "requires_confirmation": True,
        }
    )

    assert role == "Visual Data Processing Evidence"
    assert "Project" not in role
    assert "Engineer" not in role


def test_project_bullet_concept_does_not_depend_on_tailored_resume_marker() -> None:
    narrative_builder = NarrativeBuilder()

    assert narrative_builder.project_bullet_concept(
        "workflow orchestration for document generation"
    ) == "workflow"

    assert narrative_builder.project_bullet_concept(
        "workflow for tailored resume generation"
    ) is None


def test_vacancy_summary_filters_internal_alignment_labels() -> None:
    service = ResumeGenerationService()

    top_alignment = service._build_top_alignment_evidence(
        vacancy_evidence_alignment=[
            {
                "requirement": "API",
                "evidence": "Repository evidence: backend/API implementation signals",
                "confidence": "high",
            },
            {
                "requirement": "Pytest",
                "evidence": "Настроил автоматическое тестирование",
                "confidence": "high",
            },
            {
                "requirement": "CI/CD",
                "evidence": "Настройка CI/CD",
                "confidence": "high",
            },
        ],
    )

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="Backend Developer",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "responsibilities": ["Поддержка пользовательских сценариев"],
            }
        ],
        top_alignment_evidence=top_alignment,
    )

    assert "implementation signals" not in summary
    assert "Поддержка пользовательских сценариев" not in summary
    assert "настройки автоматического тестирования" in summary
    assert "настройки CI/CD" in summary
    assert "оптимизации времени ответа API на 35%" not in summary


def test_vacancy_alignment_uses_skill_fallback_when_snippets_are_missing() -> None:
    service = ResumeGenerationService()

    alignment = service._build_vacancy_evidence_alignment(
        matched_keywords=["Python", "Pytest", "Docker"],
        missing_keywords=[],
        selected_skills=["Python", "Pytest", "Docker"],
        evidence_snippets=[],
        selected_achievements=[],
    )
    top_alignment = service._build_top_alignment_evidence(
        vacancy_evidence_alignment=alignment,
    )

    assert alignment
    assert any(item["evidence"] == "Python-разработка" for item in alignment)
    assert any(item["evidence"] == "настройка автоматического тестирования" for item in alignment)
    assert any(item["evidence"] == "контейнеризация" for item in alignment)
    assert top_alignment
    assert [item["summary_phrase"] for item in top_alignment] == [
        "настройки автоматического тестирования",
        "контейнеризации",
        "Python-разработки",
    ]


def test_vacancy_alignment_maps_api_requirement_from_fastapi_skill() -> None:
    service = ResumeGenerationService()

    alignment = service._build_vacancy_evidence_alignment(
        matched_keywords=["API"],
        missing_keywords=[],
        selected_skills=["FastAPI", "Python"],
        evidence_snippets=[],
        selected_achievements=[],
    )

    assert alignment[0]["evidence"] == "разработка REST API"
    assert alignment[0]["confidence"] == "medium"


def test_top_alignment_evidence_prefers_testing_and_ci_cd_signals() -> None:
    service = ResumeGenerationService()

    top_alignment = service._build_top_alignment_evidence(
        vacancy_evidence_alignment=[
            {
                "requirement": "Python",
                "evidence": "Python-разработка",
                "confidence": "medium",
            },
            {
                "requirement": "Pytest",
                "evidence": "настройка автоматического тестирования",
                "confidence": "medium",
            },
            {
                "requirement": "CI/CD",
                "evidence": "настройка CI/CD",
                "confidence": "medium",
            },
        ],
    )

    assert [item["requirement"] for item in top_alignment] == [
        "Pytest",
        "CI/CD",
        "Python",
    ]


def test_summary_focus_drops_subsumed_generic_phrase() -> None:
    phrases = dedupe_subsumed_phrases(
        [
            "разработка REST API",
            "разработка REST API на FastAPI",
            "настройка CI/CD",
        ]
    )

    assert phrases == [
        "разработка REST API на FastAPI",
        "настройка CI/CD",
    ]


def test_summary_polishes_time_response_phrase() -> None:
    service = ResumeGenerationService()

    phrase = service._alignment_summary_phrase(
        requirement="API",
        evidence="Сократил время ответа API на 35%",
    )

    assert phrase == "оптимизации времени ответа API на 35%"


def test_resume_generation_builds_internships_from_latest_extraction() -> None:
    service = ResumeGenerationService()

    internships = service._build_internship_items(
        """
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM
Прошел 3 стажировки по
направлению Data Science:
1. Создание ИИ-системы
для мониторинга безопасности в пансионатах для пожилых
2. Автоматизированный ИИ-контроль качества
ПВХ оконных изделий по изображениям и видео
3. «ИИ-анализ текстовых
ОБРАЗОВАНИЕ
отзывов населения о социальных объектах инфраструктуры
"""
    )

    assert [item["title"] for item in internships] == [
        "ИИ-система мониторинга безопасности",
        "ИИ-контроль качества ПВХ изделий",
        "ИИ-анализ отзывов населения",
    ]
    assert all(item["category"] == "internship" for item in internships)


def test_profile_structuring_current_resume_has_three_project_like_internship_items() -> None:
    service = ProfileStructuringService()
    draft = service._build_draft(
        """
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети Прошел 3 стажировки по (промптинг), Создание нейроассистентов, Чат-боты, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.
направлению Data Science:
1. Создание ИИ-системы
Желаемая должность
для мониторинга безопасности в Prompt Engineering, Data Science, Vibe-coding пансионатах для
пожилых
ОПЫТ РАБОТЫ
(ООО «СГЦ ОПЕКА»)
2. Автоматизированный Алтайский Государственный Медицинский ИИ-контроль качества Университет, электромонтер по ремонту и
ПВХ оконных изделий обслуживанию электрооборудования по изображениям и
01.01.2015 - по настоящее время
видео (ООО «ТД «Проплекс»)
3. «ИИ-анализ текстовых
ОБРАЗОВАНИЕ
отзывов населения о социальных объектах инфраструктуры
"""
    )

    assert draft.projects == []
    assert len(draft.internships) == 3
    assert [item.title for item in draft.internships] == [
        "ИИ-система мониторинга безопасности",
        "ИИ-контроль качества ПВХ изделий",
        "ИИ-анализ отзывов населения",
    ]


def test_profile_structuring_splits_noisy_source_resume_sections() -> None:
    service = ProfileStructuringService()
    draft = service._build_draft(
        """
г.Барнаул, Россия, 656060
ул. Антона Петрова, д.262, кв. 306
(+7) 9039115133
lev.21.06.2005@gmail.com
https://github.com/Alexsey111
Перминов
Алексей
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети
Прошел 3 стажировки по
(промптинг), Создание нейроассистентов, Чат-боты, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.                       направлению Data Science:
1. Создание ИИ-системы
Желаемая должность                                                    для мониторинга
безопасности в
Prompt Engineering, Data Science, Vibe-coding                         пансионатах для
пожилых
ОПЫТ РАБОТЫ
(ООО «СГЦ ОПЕКА»)
2. Автоматизированный
Алтайский Государственный Медицинский                                 ИИ-контроль качества
Университет, электромонтер по ремонту и                               ПВХ оконных изделий
обслуживанию электрооборудования                                      по изображениям и
01.01.2015 - по настоящее время                                       видео
(ООО «ТД «Проплекс»)
3. «ИИ-анализ текстовых
ОБРАЗОВАНИЕ                                                           отзывов населения о
социальных объектах
инфраструктуры для
Алтайский государственный технический
прогнозирования
университет имени И.И. Ползунова, Барнаул
инженер, Автомобиле- и тракторостроение                               устойчивого развития
1999 - 2001
Рязанское высшее воздушно-десантное командное
училище им. В.Ф. Маргелова, Рязань
инженерный, командная тактическая воздушно-
десантных войск
1993 - 1997
Курсы
Data Science, нейронные сети, машинное обучение и
искусственный интеллект
университет искусственного интеллекта
2022
Программист на Python с нуля с помощью ChatGPT
университет зерокодинга
2023
Аналитик данных с нуля с помощью ChatGPT
университет зерокодинга
2024
Промпт-инжиниринг
университет зерокодинга
2025
"""
    )

    assert draft.contacts.email == "lev.21.06.2005@gmail.com"
    assert draft.contacts.github == "https://github.com/Alexsey111"
    assert "Python" in (draft.summary or "")
    assert "SQL" in (draft.summary or "")

    assert len(draft.experiences) == 1
    # PR-38: Парсер захватывает шум из PDF — это известное ограничение
    # Компания содержит дополнительный текст из соседних колонок
    assert "Алтайский Государственный Медицинский" in draft.experiences[0].company
    assert "Университет" in draft.experiences[0].company
    # Role содержит шум из соседних колонок PDF
    assert "электромонтер" in draft.experiences[0].role
    assert "электрооборудования" in draft.experiences[0].role

    assert [item.details for item in draft.education] == [
        (
            "Алтайский государственный технический университет "
            "им. И.И. Ползунова, Барнаул"
        ),
        (
            "Рязанское высшее воздушно-десантное командное училище "
            "им. В.Ф. Маргелова, Рязань"
        ),
    ]
    assert len(draft.courses) == 4
    assert [item.title for item in draft.internships] == [
        "ИИ-система мониторинга безопасности",
        "ИИ-контроль качества ПВХ изделий",
        "ИИ-анализ отзывов населения",
    ]

    education_text = "\n".join(item.details or "" for item in draft.education)
    assert "зерокод" not in education_text.lower()
    assert "стажиров" not in education_text.lower()
    assert "электромонтер" not in education_text.lower()


def test_profile_structuring_extracts_generic_portfolio_project_evidence() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Портфолио проектов

Цветизация изображений
Telegram bot принимает черно-белую фотографию и возвращает цветизированное изображение.
Стек: Python, neural networks, Telegram API.

Flower Shop + Telegram bot
Интернет-магазин цветов с каталогом, корзиной и уведомлениями через Telegram bot.
Стек: Python, API, SQL.

Мониторинг пансионатов
Система мониторинга безопасности в пансионатах для пожилых на основе видео и компьютерного зрения.
Стек: Python, Computer Vision.
""",
        source_file_kind="portfolio",
    )

    assert [item.title for item in draft.portfolio_projects] == [
        "Цветизация изображений",
        "Flower Shop + Telegram bot",
        "Мониторинг пансионатов",
    ]
    assert [item.category for item in draft.portfolio_projects] == [
        "portfolio_project",
        "portfolio_project",
        "portfolio_project",
    ]
    assert any(
        item.title == "Цветизация изображений"
        and "Telegram" in (item.snippet_text or "")
        for item in draft.evidence_snippets
    )
    assert all(item not in draft.projects for item in draft.portfolio_projects)


def test_profile_structuring_extracts_abstract_portfolio_projects() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Portfolio

1. Customer Analytics Dashboard
Built a dashboard for cohort analysis and operational metrics.
Stack: Python, SQL, Streamlit.
Result: reduced manual reporting work.

2. Invoice Processing Service
Implemented OCR-based extraction, validation workflow and API integration.
Technologies: Python, FastAPI, PostgreSQL.
""",
        source_file_kind="portfolio",
    )

    assert [item.title for item in draft.portfolio_projects] == [
        "Customer Analytics Dashboard",
        "Invoice Processing Service",
    ]
    assert all(item.category == "portfolio_project" for item in draft.portfolio_projects)
    assert any(
        "API" in item.skills
        for item in draft.portfolio_projects
        if item.title == "Invoice Processing Service"
    )


def test_profile_structuring_portfolio_project_count_is_not_fixed() -> None:
    service = ProfileStructuringService()

    single_project = service._build_draft(
        """
Portfolio

AI Knowledge Base
Built semantic search over internal documents.
Stack: Python, API, PostgreSQL.
""",
        source_file_kind="portfolio",
    )

    many_projects_text = "Portfolio\n\n" + "\n\n".join(
        (
            f"{index}. Automation Service {index}\n"
            f"Implemented workflow automation and API integration for use case {index}.\n"
            "Stack: Python, API, SQL."
        )
        for index in range(1, 11)
    )
    many_projects = service._build_draft(
        many_projects_text,
        source_file_kind="portfolio",
    )

    assert [item.title for item in single_project.portfolio_projects] == [
        "AI Knowledge Base"
    ]
    assert len(many_projects.portfolio_projects) == 10
    assert many_projects.portfolio_projects[0].title == "Automation Service 1"
    assert many_projects.portfolio_projects[-1].title == "Automation Service 10"


def test_evidence_bank_treats_portfolio_projects_as_project_evidence() -> None:
    service = EvidenceBankService()
    item = EvidenceBankItem(
        id="portfolio-1",
        title="Flower Shop Telegram bot",
        snippet_text="Portfolio project with Telegram bot and API.",
        source_type="resume_structured",
        category="portfolio_project",
    )

    assert service._is_project_evidence(item)


def test_resume_renderer_prints_education_before_projects() -> None:
    rendered = render_resume(
        {
            "candidate": {"full_name": "Test User"},
            "target_vacancy": {"title": "AI Specialist"},
            "sections": {
                "summary_bullets": [],
                "skills": ["Python"],
                "experience": [
                    {
                        "company": "Алтайский Государственный Медицинский Университет",
                        "role": "электромонтер по ремонту и обслуживанию электрооборудования",
                        "period": "01.2015 - н.в.",
                        "description_raw": "non-IT operational experience",
                    }
                ],
                "education": [
                    {
                        "details": (
                            "Алтайский государственный университет / "
                            "Программное обеспечение"
                        )
                    }
                ],
                "courses": [
                    {
                        "details": (
                            "Университет Зерокодинга, 2023 — "
                            "Аналитик данных с нуля с помощью ChatGPT"
                        )
                    }
                ],
                "internships": [
                    {"title": "ИИ-система мониторинга безопасности"},
                    {"title": "ИИ-контроль качества ПВХ изделий"},
                    {"title": "ИИ-анализ отзывов населения"},
                ],
                "project_sections": [
                    {
                        "project": "AI Career Copilot",
                        "role": "Backend / AI Workflow System",
                        "bullets": ["Разработал workflow анализа вакансий"],
                    }
                ],
                "selected_achievements": [],
            },
        }
    )

    assert "ОБРАЗОВАНИЕ" in rendered
    assert "ОПЫТ РАБОТЫ" in rendered
    assert "электромонтер по ремонту" in rendered
    assert "Алтайский государственный университет" in rendered
    assert "КУРСЫ" in rendered
    assert "Университет Зерокодинга" in rendered
    assert "СТАЖИРОВКИ / УЧЕБНЫЕ ПРОЕКТЫ" in rendered
    assert "ИИ-контроль качества ПВХ изделий" in rendered
    assert rendered.index("ОПЫТ РАБОТЫ") < rendered.index("ОБРАЗОВАНИЕ")
    assert rendered.index("ОБРАЗОВАНИЕ") < rendered.index("РЕЛЕВАНТНЫЕ ПРОЕКТЫ")
    assert rendered.index("КУРСЫ") < rendered.index("РЕЛЕВАНТНЫЕ ПРОЕКТЫ")
    assert rendered.index("СТАЖИРОВКИ / УЧЕБНЫЕ ПРОЕКТЫ") < rendered.index("РЕЛЕВАНТНЫЕ ПРОЕКТЫ")


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
        experience_items=[],
    )

    summary = tailoring["vacancy_aligned_summary"]
    assert summary.startswith("AI Automation Specialist с опытом")
    assert "За время работы" in summary
    assert "Среди подтверждённых результатов" not in summary
    assert "Python-разработчик и AI automation engineer" not in summary
    assert "Кандидат на позицию" not in summary
    assert "Workflow automation" in tailoring["relevant_to_vacancy"]
    assert "Python" in tailoring["relevant_to_vacancy"]
    assert "Python-based AI systems" not in tailoring["relevant_to_vacancy"]
    assert any(
        item["requirement"] == "Prompt engineering"
        and item["evidence"] == "Prompt Engineering"
        and item["confidence"] == "high"
        for item in tailoring["vacancy_evidence_alignment"]
    )
    assert any(
        item["competency"] == "Prompt engineering"
        and "prompt" in (item.get("evidence") or "").lower()
        for item in tailoring["competency_mapping"]
    )
    assert any(
        item["competency"] == "Workflow automation"
        and "workflow" in (item.get("evidence") or "").lower()
        for item in tailoring["competency_mapping"]
    )
    assert all(
        item.get("evidence") != "Technology stack from resume"
        for item in tailoring["competency_mapping"]
    )


def test_resume_vacancy_summary_builds_human_narrative_for_legal_and_medical_roles() -> None:
    service = ResumeGenerationService()

    accounting_summary = service._build_vacancy_aligned_summary(
        vacancy_title="бухгалтер",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "description_raw": (
                    "Ведение первичной бухгалтерской документации "
                    "Работа с актами, счетами, накладными и счетами-фактурами "
                    "Сверка взаиморасчётов с контрагентами"
                )
            }
        ],
    )
    supervisor_summary = service._build_vacancy_aligned_summary(
        vacancy_title="супервайзер по мерчандайзингу",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "description_raw": (
                    "Управление сменой 25 сотрудников "
                    "Контроль приёмки и отгрузки "
                    "Работа с планограммами"
                )
            }
        ],
    )
    warehouse_summary = service._build_vacancy_aligned_summary(
        vacancy_title="кладовщик",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "description_raw": (
                    "Организация складских процессов "
                    "Приёмка и отгрузка товаров "
                    "Комплектация заказов"
                )
            }
        ],
    )
    logistics_summary = service._build_vacancy_aligned_summary(
        vacancy_title="логист",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "description_raw": (
                    "Планирование маршрутов "
                    "Координация доставки "
                    "Взаимодействие с перевозчиками"
                )
            }
        ],
    )
    legal_summary = service._build_vacancy_aligned_summary(
        vacancy_title="юрист",
        selected_skills=[],
        selected_achievements=[
            {"title": "Подготовила более 250 договоров"},
        ],
        experience_items=[
            {
                "description_raw": (
                    "Подготовка договоров Судебное сопровождение "
                    "Консультирование клиентов Претензионная работа"
                )
            }
        ],
    )
    medical_summary = service._build_vacancy_aligned_summary(
        vacancy_title="терапевт",
        selected_skills=[],
        selected_achievements=[
            {"title": "Провёл более 5000 консультаций"},
        ],
        experience_items=[
            {
                "description_raw": (
                    "Диагностика пациентов Назначение лечения "
                    "Ведение медицинской документации Координация маршрутизации пациентов"
                )
            }
        ],
    )

    # PR-38: Summary без стажа т.к. нет дат в experience_items
    assert accounting_summary.startswith(
        "Бухгалтер с опытом в ведении первичной бухгалтерской документации "
    )
    assert "Работа с актами, счетами, накладными и счетами-фактурами" in accounting_summary
    assert "Сверка взаиморасчётов с контрагентами" in accounting_summary
    assert "Ведение первичной бухгалтерской документации Работа с актами" not in accounting_summary

    assert supervisor_summary.startswith(
        "Супервайзер по мерчандайзингу с опытом в управлении сменой 25 сотрудников "
    )
    assert "Контроль приёмки и отгрузки" in supervisor_summary
    assert "Работа с планограммами" in supervisor_summary
    assert "Управление сменой 25 сотрудников Контроль" not in supervisor_summary

    assert warehouse_summary.startswith(
        "Кладовщик с опытом в организации складских процессов "
    )
    assert "Приёмка и отгрузка товаров" in warehouse_summary
    assert "Комплектация заказов" in warehouse_summary
    assert "Организация складских процессов Приёмка" not in warehouse_summary

    assert logistics_summary.startswith(
        "Логист с опытом в планировании маршрутов "
    )
    assert "Координация доставки" in logistics_summary
    assert "Взаимодействие с перевозчиками" in logistics_summary
    assert "Планирование маршрутов Координация" not in logistics_summary

    assert legal_summary.startswith(
        "Юрист с опытом в подготовке договоров, судебное сопровождение и консультирование клиентов."
    )
    assert "За время работы подготовила более 250 договоров." in legal_summary
    assert "Подготовка договоров Судебное сопровождение" not in legal_summary
    assert "Среди подтверждённых результатов" not in legal_summary

    assert medical_summary.startswith(
        "Врач-терапевт с опытом в диагностика пациентов, назначение лечения и ведении медицинской документации."
    )
    assert "За время работы провёл более 5000 консультаций." in medical_summary
    assert "Диагностика пациентов Назначение лечения" not in medical_summary


def test_resume_summary_prioritizes_management_supply_signals_over_tools() -> None:
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="Заместитель начальника отдела снабжения",
        selected_skills=["Excel", "Складская логистика", "1С"],
        selected_achievements=[
            {"title": "Снизил затраты на закупки на 15%"},
            {"title": "Оптимизировал складские остатки на 25%"},
        ],
        experience_items=[
            {
                "period": "01.2015 - 03.2024",
                "description_raw": (
                    "Управление отделом снабжения\n"
                    "Планирование бюджета снабжения\n"
                    "Контроль логистических процессов\n"
                    "Ведение переговоров с поставщиками\n"
                    "Контроль исполнения договорных обязательств"
                ),
            }
        ],
        top_alignment_evidence=[],
    )

    assert summary.startswith(
        "Более 9 лет работаю в сфере материально-технического обеспечения и закупок."
    )
    assert (
        "Основной опыт связан с организацией снабжения, управлением поставщиками, "
        "бюджетированием и контролем логистических процессов."
    ) in summary
    assert "За время работы реализовал проекты по снижению затрат на закупки на 15%" in summary
    assert "оптимизации складских остатков на 25%" in summary
    assert "Руководитель в сфере материально-технического обеспечения с опытом" not in summary
    assert "с опытом Excel" not in summary


def test_resume_competency_evidence_does_not_use_private_ai_resume_narrative() -> None:
    service = ResumeGenerationService()

    prompt_evidence = service._render_competency_evidence(
        competency="Prompt engineering",
        evidence={"title": "Prompt workflow", "snippet_text": "prompt workflow", "skills": ["prompt engineering"]},
    )
    workflow_evidence = service._render_competency_evidence(
        competency="Workflow automation",
        evidence={"title": "Automation workflow", "snippet_text": "workflow automation", "skills": ["automation"]},
    )

    joined = f"{prompt_evidence} {workflow_evidence}".lower()

    assert "ai-assisted resume tailoring" not in joined
    assert "анализа вакансий" not in joined
    assert "генерации документов" not in joined
    assert "подтверждённом контексте" in joined


def test_resume_summary_fallback_is_domain_neutral_for_non_it_roles() -> None:
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="вакансия терапевт",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[],
    )

    lowered = summary.lower()
    assert lowered.startswith("врач-терапевт с опытом")
    assert "релевантных профессиональных задач" in lowered
    assert "инженерный профиль" not in lowered
    assert "прикладные инженерные задачи" not in lowered


def test_vacancy_summary_does_not_force_ai_backend_identity_for_non_it_role() -> None:
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="вакансия терапевт",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[],
    )

    lowered = summary.lower()

    assert lowered.startswith("врач-терапевт с опытом")
    assert "python-разработчик" not in lowered
    assert "ai automation engineer" not in lowered
    assert "backend-сервис" not in lowered
    assert "ai-assisted workflows" not in lowered
