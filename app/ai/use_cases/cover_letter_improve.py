# app\ai\use_cases\cover_letter_improve.py

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


async def improve_cover_letter(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    draft_text: str,
    language: str = "ru",
):
    """AI-улучшение существующего cover letter (ручной enhance-эндпоинт).

    Отдельный ``workflow_name`` (``cover_letter_improve``) от generate-path
    (``cover_letter_enhance``): generate-path исключён из подсчёта квоты
    ``ai_request`` (считается как ``generated_output`` по root-DocumentVersion),
    а ручной enhance — это полноценный AI-вызов, который должен тарифицироваться
    как ``ai_request`` (см. ``app/domain/billing.GENERATED_OUTPUT_WORKFLOWS``).
    Симметрично ``resume_enhance`` (vs ``resume_tailoring``). Промпт тот же.
    """
    return await orchestrator.execute(
        session=session,
        user_id=user_id,
        prompt_template=PromptTemplate.COVER_LETTER_ENHANCE_V1,
        prompt_vars={
            "draft": draft_text,
            "language": language,
        },
        workflow_name="cover_letter_improve",
        target_type="document",
        language=language,
    )