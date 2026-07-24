from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import AIOrchestrator
from app.ai.clients.base import BaseLLMClient
from app.services.cover_letter_generation_service import (
    CoverLetterGenerationService,
    PROJECT_DISPLAY_HINTS,
)
from app.services.text_polish.achievement_verbalizer import AchievementVerbalizer
from app.services.resume_renderer import render_cover_letter
from app.services.text_polish.humanizer import CoverLetterHumanizer
from app.services.text_polish.narrative_builder import NarrativeBuilder
from app.services.vacancy_fit_context_service import VacancyFitContextService
from app.services.vacancy_fit_narrative_service import VacancyFitNarrativeService


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
    assert "built ai system" in draft.lower()
    assert "Откликаюсь на позицию" in draft
    assert "Особенно близки задачи" in draft
    assert "Практический результат моей работы" in draft
    assert "В своей работе мне удалось показать результат через" not in draft
    assert "built ai system" in draft.lower()
    assert "Готов применять свой опыт" in draft
    assert "Со своей стороны" not in draft
    assert "Считаю себя релевантным кандидатом" not in draft
    assert "still developing experience" not in draft.lower()


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
    assert "план быстрого погружения" not in draft.lower()
    assert "Готов применять свой опыт" in draft
    assert "Со своей стороны" not in draft


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

    assert result["text"] == enhanced_text
    assert result["degraded"] is False


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

    # FastAPI и Redis были удалены AI → фолбэк на оригинал, помечаем degraded
    assert result["text"] == original_text
    assert result["degraded"] is True
    assert result["reason"] == "safety_gate_rejected"
    assert "FastAPI" in result["text"]
    assert "Redis" in result["text"]


@pytest.mark.asyncio
async def test_cover_letter_enhancement_rejects_invented_metric(
    db_session: AsyncSession,
    test_user,
):
    """Factuality-gate: AI добавил метрику, отсутствующую в оригинале → откат."""

    original_text = """I am applying for the Backend Developer position at Test Company.
My experience includes Python development and Docker containerization.
I have built several projects using these technologies, improving latency by 30%.
I am excited about this opportunity."""

    enhanced_text = """I am applying for the Backend Developer position at Test Company.
My professional experience includes Python development and Docker containerization.
I have successfully built several projects using these technologies, improving latency by 30%.
I increased overall throughput by 150% and am excited about this opportunity."""

    class InventedMetricClient(MockCoverLetterClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {"enhanced_text": enhanced_text},
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=InventedMetricClient())
    service = CoverLetterGenerationService()
    service.ai_orchestrator = orchestrator

    result = await service.enhance_cover_letter_with_ai(
        session=db_session,
        user_id=test_user.id,
        draft_text=original_text,
    )

    # 150% выдумана AI и отсутствует в оригинале → откат на оригинал
    assert result["text"] == original_text
    assert result["degraded"] is True
    assert result["reason"] == "factuality_gate_rejected"
    assert "150%" not in result["text"]
    assert "30%" in result["text"]


@pytest.mark.asyncio
async def test_cover_letter_enhancement_keeps_metric_present_in_original(
    db_session: AsyncSession,
    test_user,
):
    """Factuality-gate: метрика из оригинала сохранена — enhanced принимается."""

    original_text = """I am applying for the Backend Developer position at Test Company.
My experience includes Python development and Docker containerization.
I have built several projects using these technologies, improving latency by 30%.
I am excited about this opportunity."""

    enhanced_text = """I am applying for the Backend Developer position at Test Company.
My professional experience includes Python development and Docker containerization.
I have successfully built several projects using these technologies, improving latency by 30%.
I am excited about this opportunity to join your team."""

    class SafeMetricClient(MockCoverLetterClient):
        async def generate_structured(self, *args, **kwargs):
            return {
                "content": {"enhanced_text": enhanced_text},
                "usage": {},
            }

    orchestrator = AIOrchestrator(client=SafeMetricClient())
    service = CoverLetterGenerationService()
    service.ai_orchestrator = orchestrator

    result = await service.enhance_cover_letter_with_ai(
        session=db_session,
        user_id=test_user.id,
        draft_text=original_text,
    )

    assert result["text"] == enhanced_text
    assert result["degraded"] is False


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
    assert "опыт обработки визуальных данных" in paragraph
    assert "извлечённые факты из резюме" not in paragraph
    assert "computer vision" not in paragraph


def test_cover_letter_project_context_is_domain_neutral_for_visual_monitoring() -> None:
    narrative_builder = NarrativeBuilder()

    context = narrative_builder.cover_letter_project_phrase(
        title="Computer vision monitoring",
        body="Image and video workflow for quality control",
        skills=["computer vision", "python"],
        fact_status="confirmed",
        ownership_confidence="high",
        requires_confirmation=False,
    )

    assert context == "опыт обработки визуальных данных"
    assert "пвх" not in context.lower()
    assert "пансионат" not in context.lower()
    assert "career copilot" not in context.lower()


def test_cover_letter_project_context_uses_design_language_for_designer() -> None:
    narrative_builder = NarrativeBuilder()

    context = narrative_builder.cover_letter_project_phrase(
        title="Разработка визуальных материалов",
        body="Обработка изображений, подготовка макетов, брендинг",
        skills=["Adobe Photoshop", "Figma", "CorelDRAW"],
        fact_status="confirmed",
        ownership_confidence="high",
        requires_confirmation=False,
    )

    assert context == "разработка визуальных материалов"
    assert "визуальных данных" not in context


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
    assert "проектный опыт без расширения роли" in paragraph
    assert "Среди реализованных проектов и инициатив" in paragraph
    assert "В своей работе мне удалось показать результат через" not in paragraph
    assert "Из подтверждённого опыта особенно релевантно" not in paragraph


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
    assert "проектный опыт" in paragraph
    assert "подтверждаемый проектный контекст" not in paragraph


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
        "content-factory (Python, OpenAI)",
        "ChatGPT, LLM, AI Workflow",
    ]


def test_cover_letter_project_value_prefers_safe_evidence_phrases() -> None:
    narrative_builder = NarrativeBuilder()

    phrase = narrative_builder.cover_letter_project_value(
        selected_achievements=[
            {
                "title": "Сократил время ответа API на 35%",
                "fact_status": "confirmed",
            }
        ],
        selected_evidence=[
            {
                "title": "Repository evidence: backend/API implementation signals",
                "snippet_text": "Repository evidence indicates backend/API implementation signals.",
                "skills": ["FastAPI", "API"],
                "fact_status": "confirmed",
                "ownership_confidence": "high",
            },
            {
                "title": "Настроил автоматическое тестирование",
                "snippet_text": "Pytest test suite",
                "skills": ["Pytest"],
                "fact_status": "confirmed",
                "ownership_confidence": "high",
            },
        ],
    )

    assert phrase.startswith("настройки автоматического тестирования")
    assert "разработки REST API на FastAPI" in phrase
    assert "implementation signals" not in phrase


def test_cover_letter_project_value_verbalizes_achievements_as_connected_narrative() -> None:
    narrative_builder = NarrativeBuilder()

    phrase = narrative_builder.cover_letter_project_value(
        selected_achievements=[
            {
                "title": "Внедрил систему контроля закупок и согласования договоров",
                "fact_status": "confirmed",
            },
            {
                "title": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
            },
        ],
        selected_evidence=[],
    )

    assert phrase == (
        "внедрение системы контроля закупок и согласования договоров "
        "и сокращение сроков поставок материалов на 18%"
    )
    assert "Внедрил" not in phrase
    assert "Сократил" not in phrase


def test_cover_letter_relevance_paragraph_does_not_use_ai_project_result_template() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["Python", "FastAPI"],
        selected_achievements=[],
        selected_evidence=[
            {
                "evidence_id": "ev-1",
                "title": "Разработка REST API",
                "snippet_text": "FastAPI backend",
                "skills": ["FastAPI", "API"],
                "source_type": "resume_structured",
                "fact_status": "confirmed",
                "evidence_strength": "high",
            },
        ],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )

    assert "В своей работе мне удалось показать результат через" not in paragraph
    assert "Среди реализованных проектов и инициатив" in paragraph


def test_cover_letter_does_not_repeat_project_achievement_in_result_block() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["закупки", "поставки"],
        selected_achievements=[
            {
                "title": "Снизил затраты на закупки на 15%",
                "fact_status": "confirmed",
            },
            {
                "title": "Оптимизировал складские остатки на 25%",
                "fact_status": "confirmed",
            },
        ],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Руководитель отдела снабжения",
    )

    assert paragraph.count("снижен") <= 1
    assert paragraph.count("снижение затрат на закупки на 15%") <= 1
    assert "Среди реализованных проектов и инициатив" in paragraph
    assert "Среди результатов, которыми особенно горжусь" not in paragraph


def test_cover_letter_relevance_paragraph_leads_with_testing_evidence() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["Python", "FastAPI", "CI/CD"],
        selected_achievements=[],
        selected_evidence=[
            {
                "evidence_id": "ev-1",
                "title": "Настроил автоматическое тестирование",
                "snippet_text": "Pytest test suite",
                "skills": ["Pytest", "Testing"],
                "source_type": "resume_structured",
                "fact_status": "confirmed",
                "evidence_strength": "high",
            },
            {
                "evidence_id": "ev-2",
                "title": "Разработка REST API",
                "snippet_text": "FastAPI backend",
                "skills": ["FastAPI", "API"],
                "source_type": "resume_structured",
                "fact_status": "confirmed",
                "evidence_strength": "high",
            },
        ],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="Backend Developer",
    )

    assert paragraph.startswith("Среди реализованных проектов и инициатив")
    assert "настройки автоматического тестирования" in paragraph
    assert "разработки REST API на FastAPI" in paragraph
    assert "В своей работе мне удалось показать результат через" not in paragraph


def test_cover_letter_relevance_paragraph_uses_experience_story_tone_for_accountant() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=["первичная документация", "сверка взаиморасчётов"],
        selected_achievements=[
            {
                "title": "Сократила количество ошибок в первичных документах",
                "fact_status": "confirmed",
            },
            {
                "title": "Оптимизировала процесс сверки с контрагентами",
                "fact_status": "confirmed",
            },
        ],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=[],
        vacancy_title="бухгалтер",
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Ведение первичной бухгалтерской документации "
                    "Сверка взаиморасчётов с контрагентами "
                    "Подготовка платёжных поручений"
                )
            )
        ],
    )

    assert (
        "За время работы бухгалтером я занималась ведением первичной бухгалтерской документации, "
        "сверкой взаиморасчётов с контрагентами и подготовкой платёжных поручений."
    ) in paragraph
    assert (
        "Среди результатов, которыми особенно горжусь, — "
        "сокращение количества ошибок в первичных документах и "
        "оптимизация процесса сверки с контрагентами."
    ) in paragraph
    assert "Считаю себя релевантным кандидатом" not in paragraph
    assert "В моём опыте ближе всего" not in paragraph


def test_achievement_verbalizer_nominalizes_achievement_titles() -> None:
    verbalizer = AchievementVerbalizer()

    result = verbalizer.cover_letter_result_value(
        selected_achievements=[
            {"title": "Внедрил систему контроля закупок", "fact_status": "confirmed"},
            {"title": "Сократил сроки согласования договоров", "fact_status": "confirmed"},
        ]
    )

    assert "внедрение системы контроля закупок" in result
    assert "сокращение сроков согласования договоров" in result
    assert "внедрил" not in result
    assert "сократил" not in result


def test_achievement_verbalizer_declines_designer_nominal_tail() -> None:
    verbalizer = AchievementVerbalizer()

    result = verbalizer.nounize_achievement_phrase(
        "Разработала новый фирменный стиль компании"
    )

    assert result == "разработка нового фирменного стиля компании"
    assert "разработка новый" not in result


def test_achievement_verbalizer_declines_medical_waiting_time_tail() -> None:
    verbalizer = AchievementVerbalizer()

    result = verbalizer.nounize_achievement_phrase(
        "Сократил среднее время ожидания приёма"
    )

    assert result == "сокращение среднего времени ожидания приёма"
    assert "сокращение среднее время" not in result


def test_achievement_verbalizer_formats_result_sentence_as_connected_list() -> None:
    verbalizer = AchievementVerbalizer()

    result = verbalizer.achievement_result_sentence(
        [
            "Внедрил систему контроля закупок",
            "Сократил сроки согласования договоров",
            "Оптимизировал складские остатки",
        ]
    )

    assert result == (
        "Практический результат моей работы — "
        "внедрение системы контроля закупок, "
        "сокращение сроков согласования договоров и "
        "оптимизация складских остатков."
    )
    assert ";" not in result


def test_achievement_verbalizer_formats_resume_summary_as_action_list() -> None:
    verbalizer = AchievementVerbalizer()

    result = verbalizer.build_resume_achievement_action_sentence(
        [
            {"title": "Снизил затраты на закупки на 15%"},
            {"title": "Оптимизировал складские остатки на 25%"},
            {"title": "Сократил сроки поставок материалов на 18%"},
        ]
    )

    assert result == (
        "За время работы снизил затраты на закупки на 15%; "
        "также оптимизировал складские остатки на 25%; "
        "сократил сроки поставок материалов на 18%."
    )
    assert "Снизил" not in result
    assert "Оптимизировал" not in result
    assert "Сократил" not in result


def test_cover_letter_evidence_phrases_drop_subsumed_generic_variants() -> None:
    service = CoverLetterGenerationService()

    phrases = service._build_evidence_relevance_phrases(
        selected_evidence=[
            {
                "evidence_id": "ev-1",
                "title": "разработка REST API",
                "source_type": "resume_structured",
                "skills": ["API"],
            },
            {
                "evidence_id": "ev-2",
                "title": "разработка REST API на FastAPI",
                "source_type": "resume_structured",
                "skills": ["FastAPI", "API"],
            },
        ],
        selected_achievements=[],
    )

    assert len(phrases) == 1
    assert phrases[0].startswith("разработка REST API на FastAPI")


def test_cover_letter_gap_mitigation_dedupes_internal_automation_labels() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "Automation"},
                {"label": "Automation Tooling"},
            ]
        },
        profile_skills=[],
        vacancy_title="Backend Developer",
    )

    assert paragraph is not None
    assert "автоматизация тестирования" in paragraph
    assert "Automation" not in paragraph
    assert "Automation Tooling" not in paragraph


def test_cover_letter_gap_mitigation_uses_single_short_sentence() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "BIM-процессы"},
                {"label": "взаимодействие с экспертизой"},
                {"label": "ведение проектной документации"},
            ]
        },
        profile_skills=[],
        vacancy_title="ГИП",
    )

    assert (
        paragraph
        == "Отдельно готов обсудить план быстрого погружения: BIM-процессы и взаимодействие с экспертизой."
    )
    assert paragraph.count(".") == 1
    assert ";" not in paragraph


def test_cover_letter_gap_mitigation_filters_low_signal_pc_user_gap() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "Пользователь ПК", "classification": "hard_skill"},
            ],
            "matched_strengths": [],
        },
        profile_skills=[],
        vacancy_title="Врач",
    )

    assert paragraph is None


def test_cover_letter_gap_mitigation_filters_low_value_legal_and_accounting_gaps() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "профильного законодательства"},
                {"label": "нормотворческая деятельность"},
                {"label": "Скорость"},
                {"label": "Внимательность"},
                {"label": "Коммуникабельность"},
                {"label": "Компетентность"},
            ],
            "matched_strengths": [],
        },
        profile_skills=[],
        vacancy_title="Бухгалтер",
    )

    assert paragraph is None


def test_cover_letter_gap_mitigation_filters_direct_matches() -> None:
    service = CoverLetterGenerationService()
    narrative = VacancyFitNarrativeService().build(
        matched_keywords=["Деловая коммуникация Организаторские навыки"],
        missing_keywords=[
            "деловая коммуникация",
            "BIM-процессы",
            "взаимодействие с экспертизой",
        ],
        vacancy_evidence_alignment=[],
        selected_achievements=[],
        selected_skills=[],
    )

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative=narrative,
        profile_skills=[],
        vacancy_title="ГИП",
    )

    assert paragraph == (
        "Отдельно готов обсудить план быстрого погружения: BIM-процессы и взаимодействие с экспертизой."
    )
    assert "деловой коммуникации" not in paragraph
    assert "деловой коммуникации" not in paragraph


def test_cover_letter_gap_mitigation_filters_designer_tools_confirmed_in_profile() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {
                    "label": "отличное знание графических редакторов (Adobe Photoshop, CorelDRAW)",
                    "classification": "hard_skill",
                }
            ],
            "matched_strengths": [],
        },
        profile_skills=["Adobe Photoshop", "CorelDRAW", "Figma"],
        vacancy_title="Графический дизайнер",
    )

    assert paragraph is None


def test_cover_letter_gap_mitigation_uses_designer_skills_from_achievements() -> None:
    service = CoverLetterGenerationService()
    profile = SimpleNamespace(
        headline="Графический дизайнер",
        summary="",
        experiences=[],
        achievements=[
            SimpleNamespace(
                title="Подготовила макеты в Adobe Photoshop и CorelDRAW",
                action="",
                result="",
                skills_json=["Adobe Photoshop", "CorelDRAW"],
            )
        ],
    )

    profile_skills = service._extract_skills_from_profile(profile)
    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {
                    "label": "отличное знание графических редакторов (Adobe Photoshop, CorelDRAW)",
                    "classification": "hard_skill",
                }
            ],
            "matched_strengths": [],
        },
        profile_skills=profile_skills,
        vacancy_title="Графический дизайнер",
    )

    assert "Adobe Photoshop" in profile_skills
    assert "CorelDRAW" in profile_skills
    assert paragraph is None


def test_cover_letter_gap_mitigation_skips_education_and_certification_gaps() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "Высшее образование", "classification": "education"},
                {"label": "сертификат специалиста", "classification": "certification"},
                {"label": "мерчандайзинг", "classification": "skill"},
            ]
        },
        profile_skills=[],
        vacancy_title="Retail Supervisor",
    )

    assert paragraph == (
        "Отдельно готов обсудить план быстрого погружения: мерчандайзинг."
    )
    assert "образование" not in paragraph.lower()
    assert "сертификат" not in paragraph.lower()


def test_cover_letter_gap_focus_uses_requested_cases() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "мерчандайзинг"},
                {"label": "полевой аудит торговых точек"},
                {"label": "профильное законодательство"},
                {"label": "нормотворческая деятельность"},
            ]
        },
        profile_skills=[],
        vacancy_title="Mixed role",
    )

    assert paragraph == (
        "Отдельно готов обсудить план быстрого погружения: "
        "мерчандайзинг и полевой аудит торговых точек."
    )
    assert "профильном законодательстве" not in paragraph
    assert "нормотворческой деятельности" not in paragraph


def test_cover_letter_alignment_sections_are_evidence_grounded() -> None:
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

    context = VacancyFitContextService().build(
        matched_keywords=["prompt engineering"],
        missing_keywords=[],
        selected_skills=["ChatGPT", "LLM", "prompt engineering"],
        evidence_snippets=selected_evidence,
        selected_achievements=[],
    )
    narrative = context["vacancy_fit_narrative"]

    assert context["vacancy_evidence_alignment"][0]["confidence"] == "high"
    assert narrative["matched_strengths"][0]["label"].casefold() == "prompt engineering"


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


def test_cover_letter_closing_uses_business_management_context() -> None:
    service = CoverLetterGenerationService()

    closing = service._build_closing(
        vacancy_title="Заместитель начальника отдела снабжения",
        company="Test Company",
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Организация закупочной деятельности\n"
                    "Контроль поставок\n"
                    "Ведение переговоров с поставщиками"
                )
            )
        ],
        selected_skills=["Материально-техническое обеспечение", "Бюджетирование"],
    )

    lowered = closing.lower()
    assert "организации закупок" in lowered
    assert "контроле поставок" in lowered
    assert "работе с поставщиками" in lowered
    assert "снижении затрат на снабжение" in lowered
    assert "ответственность за результат" not in lowered


def test_cover_letter_uses_business_value_closing_for_supply_management_role() -> None:
    service = CoverLetterGenerationService()

    closing = service._build_closing(
        vacancy_title="Руководитель отдела снабжения",
        company="Test Company",
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Организация закупочной деятельности\n"
                    "Контроль поставок\n"
                    "Работа с поставщиками\n"
                    "Снижение затрат на снабжение"
                )
            )
        ],
        selected_skills=["Закупочная деятельность", "Материально-техническое обеспечение"],
    )

    lowered = closing.lower()
    assert "организации закупок" in lowered
    assert "контроле поставок" in lowered
    assert "работе с поставщиками" in lowered
    assert "снижении затрат на снабжение" in lowered
    assert "аккуратное выполнение задач" not in lowered
    assert "ответственность за результат" not in lowered


def test_cover_letter_closing_does_not_use_supply_template_for_lawyer() -> None:
    service = CoverLetterGenerationService()

    closing = service._build_closing(
        vacancy_title="Юрист",
        company="Test Company",
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Подготовка договоров\n"
                    "Судебное сопровождение\n"
                    "Консультирование клиентов"
                )
            )
        ],
        selected_skills=["Договорная работа", "Гражданское право", "Арбитраж"],
        matched_keywords=["Договорная работа", "Претензионная работа"],
    )

    lowered = closing.lower()
    assert "организации закупок" not in lowered
    assert "контроле поставок" not in lowered
    assert "работе с поставщиками" not in lowered
    assert "снижении затрат на снабжение" not in lowered
    assert "юрист," not in lowered
    assert "подготовила более 250 договоров" not in lowered
    assert "договор" in lowered


def test_cover_letter_closing_does_not_use_supply_template_for_plumber() -> None:
    service = CoverLetterGenerationService()

    closing = service._build_closing(
        vacancy_title="Сантехник",
        company="Test Company",
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Монтаж систем водоснабжения и канализации\n"
                    "Обслуживание сантехнического оборудования\n"
                    "Замена трубопроводов"
                )
            )
        ],
        selected_skills=["Монтаж систем водоснабжения", "Ремонт трубопроводов"],
        matched_keywords=["Монтаж систем водоснабжения", "Обслуживание оборудования"],
    )

    lowered = closing.lower()
    assert "организации закупок" not in lowered
    assert "снижении затрат на снабжение" not in lowered
    assert "сантехника," not in lowered
    assert "слесарь-сантехник" not in lowered
    assert "водоснаб" in lowered or "трубопровод" in lowered


def test_cover_letter_closing_filters_role_and_achievement_noise() -> None:
    service = CoverLetterGenerationService()

    closing = service._build_closing(
        vacancy_title="Юрист",
        company="Test Company",
        candidate_experiences=[],
        selected_skills=[
            "Юрист",
            "Гражданское право",
            "Договорное право",
            "Арбитраж",
            "Legal Research",
            "Документооборот",
            "Подготовила более 250 договоров",
        ],
        matched_keywords=[],
    )

    lowered = closing.lower()
    assert "юрист," not in lowered
    assert "legal research" not in lowered
    assert "подготовила более 250 договоров" not in lowered
    assert "готов применять накопленный опыт в юрист" not in lowered


def test_cover_letter_scope_list_normalizes_budgeting_case() -> None:
    humanizer = CoverLetterHumanizer()

    result = humanizer.scope_list(
        "организацию закупочной деятельности, управление складскими запасами, "
        "ведение переговоров с поставщиками, бюджетирования"
    )

    assert "бюджетирования" not in result
    assert "бюджетирование" in result


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
        candidate_experiences=[],
        selected_skills=[],
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
    assert "Откликаюсь на позицию Backend Developer в Test Company" in rendered
    assert "Сейчас мой основной профессиональный фокус" in rendered
    assert "Особенно близки задачи, связанные с Python" in rendered
    assert "Среди реализованных проектов и инициатив" in rendered
    assert "В своей работе мне удалось показать результат через" not in rendered
    assert "Готов применять свой опыт" in rendered
    assert "Со своей стороны" not in rendered
    assert "Буду рад обсудить" in rendered

    assert "Dear hiring team" not in rendered
    assert "Thank you for your consideration" not in rendered
    assert "confirmed overlap" not in rendered
    assert "needs_confirmation" not in rendered
    assert "Из подтверждённого опыта особенно релевантно" not in rendered
    assert "усилить доменную практику" not in rendered
    assert "Считаю себя релевантным кандидатом" not in rendered
    assert "на пересечении профессионального опыта" not in rendered


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


def test_cover_letter_generic_role_framing_is_domain_neutral() -> None:
    service = CoverLetterGenerationService()

    framing = service._cover_letter_focus_from_headline(headline=None)

    lowered = framing.lower()
    assert "профессионального опыта" in lowered
    assert "инженерного опыта" not in lowered
    assert "автоматизации" not in lowered


def test_cover_letter_gap_mitigation_filters_soft_skills() -> None:
    """Soft skills не должны попадать в gap mitigation paragraph."""
    service = CoverLetterGenerationService()

    paragraph = service._build_gap_mitigation_paragraph(
        vacancy_fit_narrative={
            "critical_gaps": [
                {"label": "Ответственность"},
                {"label": "Внимательность"},
                {"label": "Docker"},
                {"label": "Коммуникабельность"},
            ],
            "matched_strengths": [],
        },
        profile_skills=[],
        vacancy_title="Python Developer",
    )

    assert paragraph is not None
    assert "ответственност" not in (paragraph or "").lower()
    assert "внимательн" not in (paragraph or "").lower()
    assert "коммуникабельн" not in (paragraph or "").lower()
    assert "docker" in (paragraph or "").lower()


def test_cover_letter_join_experience_phrases_limits_to_three_and_uses_human_format() -> None:
    """PR-34: Проверка объединения experience phrases в человеческую фразу."""
    humanizer = CoverLetterHumanizer()

    # 1 фраза
    assert humanizer.join_experience_phrases(["монтажа систем водоснабжения"]) == "монтажа систем водоснабжения"

    # 2 фразы — через "и"
    assert (
        humanizer.join_experience_phrases(["монтажа систем водоснабжения", "обслуживания оборудования"])
        == "монтажа систем водоснабжения и обслуживания оборудования"
    )

    # 3 фразы — через запятую и "и"
    assert (
        humanizer.join_experience_phrases([
            "монтажа систем водоснабжения",
            "обслуживания оборудования",
            "замены трубопроводов",
        ])
        == "монтажа систем водоснабжения, обслуживания оборудования и замены трубопроводов"
    )

    # 4+ фразы — обрезаются до 3
    assert (
        humanizer.join_experience_phrases([
            "разработки API",
            "настройки CI/CD",
            "тестирования",
            "документирования",
        ])
        == "разработки API, настройки CI/CD и тестирования"
    )

    # Пустой список
    assert humanizer.join_experience_phrases([]) == ""


def test_cover_letter_compress_experience_phrases_groups_plumbing_activities() -> None:
    """PR-36: Проверка группировки сантехнических активностей."""
    narrative_builder = NarrativeBuilder()

    # Группировка монтажа и обслуживания
    assert narrative_builder.compress_experience_phrases([
        "монтажа систем водоснабжения",
        "обслуживания оборудования",
    ]) == ["монтажа и обслуживания инженерных систем"]

    # Группировка трубопроводов
    assert narrative_builder.compress_experience_phrases([
        "замены трубопроводов",
        "ремонта труб",
    ]) == ["ремонта трубопроводов"]

    # Группировка аварий
    assert narrative_builder.compress_experience_phrases([
        "устранения аварийных протечек",
        "устранения аварий",
    ]) == ["устранения аварийных ситуаций"]

    # Смешанные фразы — часть группируется, часть остаётся
    result = narrative_builder.compress_experience_phrases([
        "монтажа систем водоснабжения",
        "обслуживания оборудования",
        "замены трубопроводов",
        "устранения аварий",
    ])
    assert "монтажа и обслуживания инженерных систем" in result
    assert "ремонта трубопроводов" in result or "замены трубопроводов" in result
    assert "устранения аварийных ситуаций" in result

    # Диагностика и осмотры
    assert narrative_builder.compress_experience_phrases([
        "проведения профилактических осмотров",
        "диагностики оборудования",
    ]) == ["проведения профилактических осмотров"]

    # Пустой список
    assert narrative_builder.compress_experience_phrases([]) == []

    # Одна фраза без группировки
    assert narrative_builder.compress_experience_phrases(["разработки API"]) == ["разработки API"]


def test_cover_letter_experience_value_uses_compression_for_plumber_resume() -> None:
    """PR-36: Проверка что experience value использует сжатие для сантехнического резюме."""
    import re
    service = CoverLetterGenerationService()
    narrative_builder = NarrativeBuilder()

    experience_value = narrative_builder.cover_letter_experience_value(
        vacancy_title="Сантехник",
        matched_keywords=["сантехника", "инженерные системы"],
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Монтаж систем водоснабжения и канализации\n"
                    "Обслуживание сантехнического оборудования\n"
                    "Замена трубопроводов\n"
                    "Устранение аварийных ситуаций\n"
                    "Установка сантехнических приборов\n"
                    "Проведение профилактических осмотров"
                )
            ),
        ],
        is_supply_management_context=service._is_supply_management_context,
        compress_experience_phrases=narrative_builder.compress_experience_phrases,
    )

    # Проверяем что фразы сжаты в обобщённые категории
    assert "монтажа и обслуживания инженерных систем" in experience_value.lower() or (
        "монтаж" in experience_value.lower() and "обслуживани" in experience_value.lower()
    )
    # Не должно быть больше 3 элементов
    parts = [p.strip() for p in re.split(r",| и ", experience_value) if p.strip()]
    assert len(parts) <= 3


def test_cover_letter_relevance_paragraph_uses_supply_management_experience() -> None:
    service = CoverLetterGenerationService()

    paragraph = service._build_relevance_paragraph(
        matched_keywords=[
            "договоры",
            "претензионная работа",
            "взаимодействие с заказчиком",
            "поставщики",
            "МТС",
        ],
        selected_achievements=[],
        selected_evidence=[],
        missing_keywords=[],
        profile_skills=["Excel", "1С"],
        vacancy_title="Заместитель начальника отдела снабжения",
        candidate_experiences=[
            SimpleNamespace(
                description_raw=(
                    "Организация закупочной деятельности\n"
                    "Управление складскими запасами\n"
                    "Ведение переговоров с поставщиками\n"
                    "Контроль поставок\n"
                    "Контроль исполнения договорных обязательств\n"
                    "Претензионная работа"
                )
            )
        ],
    )

    lowered = paragraph.lower()
    assert "мой опыт включает" in lowered
    assert "организаци" in lowered and "закуп" in lowered
    assert "складск" in lowered and "запас" in lowered
    assert "переговор" in lowered and "поставщик" in lowered
    assert "контрол" in lowered and "постав" in lowered
    assert "договор" in lowered
    assert "аккуратное выполнение задач" not in lowered
    assert "ответственност" not in lowered
    assert "быстро включ" not in lowered


# --- Bug#75: фильтр мусорных title'ов в cover letter ------------------------
# Юзер (ZEBRA-репорт) видел в сопроводительном письме sub-bullets из
# секций «Роль:», «Дополнительное обучение», «Дополнительно» и т.п.
# В БД они лежат с fact_status="confirmed", потому что extraction
# (после a8d0ced) теперь ловит markdown `*` буллеты. cover letter НЕ
# должен их использовать — это section headings / названия курсов, а не
# реальные ачивки. Закрываем на уровне _get_confirmed_achievements.


def test_is_garbage_achievement_title_filters_zebra_mushroom_titles() -> None:
    """Регрессия Bug#75: 6 мусорных title'ов из ZEBRA-репорта отсеиваются."""
    service = CoverLetterGenerationService()

    garbage = [
        # «Роль:» / «**Роль:**» section headings (под-булет из ПРОЕКТЫ).
        "**Роль:** Проектирование архитектуры, реализация MVP, интеграция LLM, продуктовая логика",
        "Роль: построение архитектуры",
        # Курсы из секции «ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ» (год в скобках).
        "* Data Science и нейросети (2022)",
        "* Python разработка с ChatGPT (2023)",
        "* Аналитика данных (2024)",
        "Prompt Engineering (2025)",
        "AI/Neural Networks PRO (2026)",
        # Под-булеты из «ДОПОЛНИТЕЛЬНО» (нет action verb).
        "* Упор на прикладную разработку и быстрые итерации продуктов",
        "* Фокус на LLM, автоматизации и создании AI-агентов",
        "* Ориентация на продуктовую разработку, а не только код",
        # Section heading без хвоста.
        "Дополнительно",
        "Практический опыт",
    ]
    for title in garbage:
        assert service._is_garbage_achievement_title(title) is True, title


def test_is_garbage_achievement_title_keeps_real_achievements() -> None:
    """Регрессия Bug#75: реальные достижения НЕ отсеиваются фильтром."""
    service = CoverLetterGenerationService()

    real = [
        "Разработал FastAPI сервис для обработки 10K RPS",
        "Снизил latency на 30%",
        "Создал AI-платформу для упрощения онбординга",
        "Внедрил CI/CD, ускорив деплой с 30 до 5 минут",
        # Под-булет с глаголом результата — должен пройти.
        "* Создал RAG-систему для команды из 5 человек",
        "* Внедрил автоматизацию, сократив ручную работу на 80%",
        "AI-платформа для анализа вакансий и подготовки кандидатов.",
    ]
    for title in real:
        assert service._is_garbage_achievement_title(title) is False, title


def test_get_confirmed_achievements_excludes_zebra_mushroom_titles() -> None:
    """Регрессия Bug#75: cover letter НЕ получает мусорные title'ы
    даже если в БД у них fact_status=confirmed."""
    service = CoverLetterGenerationService()

    profile_achievements = [
        SimpleNamespace(
            id="real-1",
            title="Снизил latency на 30%",
            fact_status="confirmed",
            situation=None, task=None, action=None, result=None, metric_text=None,
        ),
        SimpleNamespace(
            id="garbage-1",
            title="**Роль:** Проектирование архитектуры, реализация MVP",
            fact_status="confirmed",
            situation=None, task=None, action=None, result=None, metric_text=None,
        ),
        SimpleNamespace(
            id="garbage-2",
            title="* Упор на прикладную разработку и быстрые итерации продуктов",
            fact_status="confirmed",
            situation=None, task=None, action=None, result=None, metric_text=None,
        ),
        SimpleNamespace(
            id="garbage-3",
            title="* Data Science и нейросети (2022)",
            fact_status="confirmed",
            situation=None, task=None, action=None, result=None, metric_text=None,
        ),
        SimpleNamespace(
            id="real-2",
            title="* Создал RAG-систему для команды из 5 человек",
            fact_status="confirmed",
            situation=None, task=None, action=None, result=None, metric_text=None,
        ),
        # НЕ confirmed — не должны попасть независимо от мусорности.
        SimpleNamespace(
            id="pending-1",
            title="**Роль:** Должен быть отфильтрован по fact_status",
            fact_status="needs_confirmation",
            situation=None, task=None, action=None, result=None, metric_text=None,
        ),
    ]

    confirmed = service._get_confirmed_achievements(profile_achievements)

    ids = [item["id"] for item in confirmed]
    assert ids == ["real-1", "real-2"], f"unexpected order/filter: {ids}"
