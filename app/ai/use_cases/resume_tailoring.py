# app\ai\use_cases\resume_tailoring.py

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate


async def tailor_resume(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    vacancy,
    analysis,
    profile,
    achievements,
):
    """AI-адаптация резюме под вакансию.

    Сервис передаёт готовые доменные объекты;
    use case решает, какие поля извлечь и какой промпт применить.
    """
    return await orchestrator.execute(
        session=session,
        user_id=user_id,
        prompt_template=PromptTemplate.RESUME_TAILOR_V1,
        prompt_vars={
            "vacancy_title": vacancy.title,
            "company": vacancy.company,
            "must_have": [item.get("text") for item in analysis.must_have_json],
            "profile_summary": profile.summary or "",
            "confirmed_achievements": [ach["title"] for ach in achievements],
        },
        workflow_name="resume_tailoring",
        target_type="vacancy",
        target_id=str(vacancy.id),
    )
