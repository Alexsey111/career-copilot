# app\schemas\profile_import.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResumeImportRequest(BaseModel):
    source_file_id: UUID


class ResumeImportResponse(BaseModel):
    profile_id: UUID
    source_file_id: UUID
    extraction_id: UUID
    status: str
    detected_format: str
    text_length: int
    text_preview: str
    created_at: datetime