# app\api\ai\registry\prompts.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PromptTemplate(str, Enum):
    """Реестр промптов с версионированием"""
    # Resume tailoring
    RESUME_TAILOR_V1 = "resume_tailor_v1"
    RESUME_TAILOR_V2 = "resume_tailor_v2"  # с gap-mitigation
    
    # Resume enhancement
    RESUME_ENHANCE_V1 = "resume_enhance_v1"
    
    # Cover letter
    COVER_LETTER_V1 = "cover_letter_v1"
    COVER_LETTER_GAP_MITIGATION = "cover_letter_gap_mitigation_v1"
    
    # Cover letter enhancement
    COVER_LETTER_ENHANCE_V1 = "cover_letter_enhance_v1"
    
    # Interview prep
    INTERVIEW_QUESTIONS_V1 = "interview_questions_v1"
    INTERVIEW_FEEDBACK_V1 = "interview_feedback_v1"

    # Interview coach
    INTERVIEW_COACH_V1 = "interview_coach_v1"


@dataclass(frozen=True)
class PromptSpec:
    """Спецификация промпта: шаблон + входная схема + выходная схема"""
    template: str
    input_schema: dict[str, Any]  # описание ожидаемых переменных
    output_schema: dict[str, Any] | None = None  # для structured output
    model_hint: str | None = None  # рекомендация по модели
    temperature_hint: float | None = None


PROMPT_REGISTRY: dict[PromptTemplate, PromptSpec] = {
    PromptTemplate.RESUME_TAILOR_V1: PromptSpec(
        template="""
Ты — эксперт по составлению резюме для российского рынка труда.
Задача: адаптируй резюме кандидата под конкретную вакансию, сохраняя фактологичность.

Входные данные:
- Вакансия: {vacancy_title} в {company}
- Требования: {must_have}
- Профиль кандидата: {profile_summary}
- Подтверждённые достижения: {confirmed_achievements}

Правила:
1. Используй только подтверждённые факты (fact_status=confirmed)
2. Вынеси совпадающие навыки в начало раздела "Ключевые навыки"
3. Не добавляй выдуманные метрики или опыт
4. Формат: линейный текст, без таблиц, с заголовками на русском

Выведи адаптированное резюме в формате:
{{
  "summary": "...",
  "skills": ["...", "..."],
  "experience_highlights": ["...", "..."]
}}
""".strip(),
        input_schema={
            "vacancy_title": "str",
            "company": "str",
            "must_have": "list[str]",
            "profile_summary": "str",
            "confirmed_achievements": "list[str]",
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "experience_highlights": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "skills"],
        },
    ),
    
    PromptTemplate.RESUME_ENHANCE_V1: PromptSpec(
        template="""You are an ATS resume editor.

STRICT RULES:
- Do NOT add any new facts
- Do NOT invent metrics
- Do NOT change meaning
- Only improve clarity, impact, and wording

IMPORTANT:
- Respond ONLY in {language}. Do NOT mix languages.

Input resume:
{resume_text}

Return JSON:
{{
  "enhanced_text": "..."
}}
""".strip(),
        input_schema={
            "resume_text": "str",
            "language": "str",
        },
        output_schema={
            "type": "object",
            "properties": {
                "enhanced_text": {"type": "string"},
            },
            "required": ["enhanced_text"],
        },
    ),
    
    PromptTemplate.COVER_LETTER_ENHANCE_V1: PromptSpec(
        template="""You are a professional cover letter editor.

STRICT RULES:
- Do NOT add new experience
- Do NOT invent skills
- Do NOT remove gaps
- Improve clarity and tone

IMPORTANT:
- Respond ONLY in {language}. Do NOT mix languages.

Input:
{draft}

Return JSON:
{{
  "enhanced_text": "..."
}}
""".strip(),
        input_schema={
            "draft": "str",
            "language": "str",
        },
        output_schema={
            "type": "object",
            "properties": {
                "enhanced_text": {"type": "string"},
            },
            "required": ["enhanced_text"],
        },
    ),
    PromptTemplate.INTERVIEW_COACH_V1: PromptSpec(
        template="""You are an interview coach.

STRICT RULES:
- Do NOT add new experience
- Do NOT invent metrics
- Do NOT change facts
- Only restructure and improve clarity

Question: {question}

User answer: {answer}

Evaluation: {evaluation}

Rewrite the answer using STAR format.

IMPORTANT:
- Respond ONLY in {language}. Do NOT mix languages.

Return JSON:
{{
  "improved_answer": "...",
  "explanation": "what was improved"
}}
""".strip(),
        input_schema={
            "question": "str",
            "answer": "str",
            "evaluation": "str",
            "language": "str",
        },
        output_schema={
            "type": "object",
            "properties": {
                "improved_answer": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["improved_answer"],
        },
    ),
}


def get_prompt(template: PromptTemplate) -> PromptSpec:
    """Получить спецификацию промпта по ключу"""
    if template not in PROMPT_REGISTRY:
        raise ValueError(f"Unknown prompt template: {template}")
    return PROMPT_REGISTRY[template]