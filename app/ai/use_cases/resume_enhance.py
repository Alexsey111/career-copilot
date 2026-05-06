# app\ai\use_cases\resume_enhance.py

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


async def enhance_resume(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    resume_text: str,
    language: str = "ru",
):
    """AI-улучшение текста резюме (без добавления фактов).

    Сервис передаёт только текст и язык;
    use case знает, какой промпт и схему использовать.
    """
    return await orchestrator.execute(
        session=session,
        user_id=user_id,
        prompt_template=PromptTemplate.RESUME_ENHANCE_V1,
        prompt_vars={
            "resume_text": resume_text,
            "language": language,
        },
        workflow_name="resume_enhance",
        target_type="document",
        language=language,
    )
