# app/ai/registry/prompts.py
from __future__ import annotations

from enum import Enum


class PromptTemplate(str, Enum):
    """Реестр промптов с версионированием"""

    # Resume tailoring
    RESUME_TAILOR_V1 = "resume_tailor_v1"
    RESUME_TAILOR_V2 = "resume_tailor_v2"  # с gap-mitigation

    # Resume enhancement
    RESUME_ENHANCE_V1 = "resume_enhance_v1"

    # Cover letter
    COVER_LETTER_V1 = "cover_letter_v1"
    COVER_LETTER_V2 = "cover_letter_v2"  # с gap-mitigation

    # Cover letter enhancement
    COVER_LETTER_ENHANCE_V1 = "cover_letter_enhance_v1"

    # Interview prep
    INTERVIEW_PREP_V1 = "interview_prep_v1"

    # Interview coach
    INTERVIEW_COACH_V1 = "interview_coach_v1"

    # Analysis
    VACANCY_ANALYSIS_V1 = "vacancy_analysis_v1"


PROMPT_SPECS = {
    PromptTemplate.RESUME_ENHANCE_V1: {
        "prompt_spec": """You are an ATS resume editor.

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
{
  "enhanced_text": "..."
}""",
        "output_schema": {
            "type": "object",
            "properties": {
                "enhanced_text": {"type": "string"},
            },
            "required": ["enhanced_text"],
        },
    },
    PromptTemplate.COVER_LETTER_ENHANCE_V1: {
        "prompt_spec": """You are a professional cover letter editor.

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
{
  "enhanced_text": "..."
}""",
        "output_schema": {
            "type": "object",
            "properties": {
                "enhanced_text": {"type": "string"},
            },
            "required": ["enhanced_text"],
        },
    },
    PromptTemplate.INTERVIEW_COACH_V1: {
        "prompt_spec": """You are an interview coach.

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
{
  "improved_answer": "...",
  "explanation": "what was improved"
}""",
        "output_schema": {
            "type": "object",
            "properties": {
                "improved_answer": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["improved_answer"],
        },
    },
}

