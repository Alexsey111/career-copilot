from __future__ import annotations

from app.ai.use_cases.cover_letter_enhance import enhance_cover_letter
from app.ai.use_cases.interview_coach import coach_answer, coach_attempts
from app.ai.use_cases.resume_enhance import enhance_resume
from app.ai.use_cases.resume_tailoring import tailor_resume

__all__ = [
    "coach_answer",
    "coach_attempts",
    "enhance_cover_letter",
    "enhance_resume",
    "tailor_resume",
]
