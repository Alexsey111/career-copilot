# app\ai\use_cases\resume_tailoring.py

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator
from app.ai.registry.prompts import PromptTemplate
from app.domain.markets import normalize_market

# Локализация рыночного контекста промпта RESUME_TAILOR_V1 (Этап 7).
# Промпт остаётся «глупым» — локализация сосредоточена в Python-коде (testable).
MARKET_PROMPT_LABELS = {
    "ru": "российского рынка труда",
    "eu": "EU job market",
    "us": "US job market",
}

MARKET_SECTION_LANGUAGE = {
    "ru": "русском",
    "eu": "English (EU)",
    "us": "English (US)",
}


async def tailor_resume(
    orchestrator: AIOrchestrator,
    session,
    *,
    user_id,
    vacancy,
    analysis,
    profile,
    achievements,
    market: str = "ru",
):
    """AI-адаптация резюме под вакансию.

    Сервис передаёт готовые доменные объекты;
    use case решает, какие поля извлечь и какой промпт применить.
    ``market`` (RU/EU/US) параметризует рыночный контекст промпта.
    """
    market_key = normalize_market(market)
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
            "market_label": MARKET_PROMPT_LABELS[market_key],
            "section_language": MARKET_SECTION_LANGUAGE[market_key],
        },
        workflow_name="resume_tailoring",
        target_type="vacancy",
        target_id=str(vacancy.id),
    )
