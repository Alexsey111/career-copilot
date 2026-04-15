# app\schemas\profile_structured.py

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class StructuredProfileExtractRequest(BaseModel):
    extraction_id: UUID


class StructuredProfileExtractResponse(BaseModel):
    profile_id: UUID
    extraction_id: UUID
    full_name: str | None
    headline: str | None
    location: str | None
    target_roles: list[str]
    experience_count: int
    warnings: list[str]