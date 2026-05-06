# app\ai\use_cases\cover_letter_enhance.py

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


async def enhance_cover_letter(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    draft_text: str,
    language: str = "ru",
):
    """AI-улучшение текста сопроводительного письма.

    Сервис передаёт только draft и язык;
    use case знает, какой промпт и схему использовать.
    """
    return await orchestrator.execute(
        session=session,
        user_id=user_id,
        prompt_template=PromptTemplate.COVER_LETTER_ENHANCE_V1,
        prompt_vars={
            "draft": draft_text,
            "language": language,
        },
        workflow_name="cover_letter_enhance",
        target_type="document",
        language=language,
    )
