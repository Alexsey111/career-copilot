# app\schemas\profile_structured.py

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class StructuredProfileExtractRequest(BaseModel):
    extraction_id: UUID


class StructuredProfileExtractResponse(BaseModel):
    profile_id: UUID
    extraction_id: UUID
    full_name: str | None
    headline: str | None
    location: str | None
    contacts: dict[str, str | None] = Field(default_factory=dict)
    target_roles: list[str]
    experience_count: int
    project_count: int = 0
    internship_count: int = 0
    achievement_signal_count: int = 0
    evidence_snippet_count: int = 0
    technologies: list[str] = Field(default_factory=list)
    ai_tools: list[str] = Field(default_factory=list)
    automation_tools: list[str] = Field(default_factory=list)
    competency_signal_count: int = 0
    structured_evidence: list[dict] = Field(default_factory=list)
    warnings: list[str]
