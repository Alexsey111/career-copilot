from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class IntakePersonal(BaseModel):
    name: str | None = None
    location: str | None = None
    target_role: str | None = None


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
    repositories: list[GitHubRepositoryIntake] = Field(default_factory=list)


class GitHubPublicProfileImportRequest(BaseModel):
    profile_url: str
    target_role: str | None = None
    max_repositories: int = Field(default=12, ge=1, le=30)
    include_readme: bool = True


class ProfileIntakeResponse(BaseModel):
    profile_id: UUID
    source_file_id: UUID
    extraction_id: UUID
    source: Literal["manual", "github", "github_public"]
    status: str
    full_name: str | None
    location: str | None
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
