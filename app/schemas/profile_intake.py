# app\schemas\profile_intake.py

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.domain.markets import Market


class IntakePersonal(BaseModel):
    name: str | None = None
    location: str | None = None
    target_role: str | None = None
    market: Market | None = None


class IntakeSkills(BaseModel):
    technologies: list[str] = Field(default_factory=list)
    ai_tools: list[str] = Field(default_factory=list)
    automation_tools: list[str] = Field(default_factory=list)


class IntakeExperience(BaseModel):
    company_or_project: str
    role: str | None = None
    what_did_you_do: str
    technologies: list[str] = Field(default_factory=list)
    results: str | None = None


class IntakeProject(BaseModel):
    title: str
    description: str
    stack: list[str] = Field(default_factory=list)
    results: str | None = None


class IntakeEducation(BaseModel):
    title: str
    institution: str | None = None
    details: str | None = None


class ManualProfileIntakeRequest(BaseModel):
    personal: IntakePersonal = Field(default_factory=IntakePersonal)
    skills: IntakeSkills = Field(default_factory=IntakeSkills)
    experience: list[IntakeExperience] = Field(default_factory=list)
    projects: list[IntakeProject] = Field(default_factory=list)
    education: list[IntakeEducation] = Field(default_factory=list)


class GitHubRepositoryIntake(BaseModel):
    name: str
    description: str | None = None
    stack: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    url: str | None = None


class GitHubProfileIntakeRequest(BaseModel):
    username: str
    profile_url: str | None = None
    target_role: str | None = None
    market: Market | None = None
    repositories: list[GitHubRepositoryIntake] = Field(default_factory=list)


class GitHubPublicProfileImportRequest(BaseModel):
    # Bug#30a: фронт раньше слал `github_url`, бэк ждал `profile_url` → 422.
    # Чтобы старые клиенты не падали, принимаем оба ключа в `profile_url`.
    profile_url: str | None = None
    github_url: str | None = None
    target_role: str | None = None
    market: Market | None = None
    max_repositories: int = Field(default=12, ge=1, le=30)
    include_readme: bool = True

    @model_validator(mode="after")
    def _resolve_profile_url(self) -> "GitHubPublicProfileImportRequest":
        # Если profile_url пустое, но прислали github_url (старый фронт) — берём его.
        if not self.profile_url and self.github_url:
            object.__setattr__(self, "profile_url", self.github_url)
        if not self.profile_url:
            raise ValueError("profile_url is required")
        return self


class ProfileIntakeResponse(BaseModel):
    profile_id: UUID
    source_file_id: UUID
    extraction_id: UUID
    source: Literal["manual", "github", "github_public"]
    status: str
    full_name: str | None
    location: str | None
    market: Market | None = None
    target_roles: list[str]
    experience_count: int
    project_count: int
    achievement_count: int
    evidence_snippet_count: int
    technologies: list[str]
    ai_tools: list[str]
    automation_tools: list[str]
    raw_text_preview: str
    created_at: datetime


class MarketUpdateRequest(BaseModel):
    market: Market
