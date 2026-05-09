# app\schemas\resume_generation.py

from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeAchievement(BaseModel):
    title: str
    relevance_score: float = Field(ge=0, le=1)


class ResumeExperience(BaseModel):
    company: str
    role: str
    start_date: str | None = None
    end_date: str | None = None

    selected_achievements: list[ResumeAchievement] = Field(default_factory=list)


class GeneratedResume(BaseModel):
    target_role: str | None = None

    summary: str | None = None

    skills: list[str] = Field(default_factory=list)

    experiences: list[ResumeExperience] = Field(default_factory=list)

    matched_keywords: list[str] = Field(default_factory=list)

    missing_keywords: list[str] = Field(default_factory=list)