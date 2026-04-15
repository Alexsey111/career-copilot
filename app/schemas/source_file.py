# app\schemas\source_file.py

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_kind: str
    original_name: str
    mime_type: str | None
    size_bytes: int | None
    created_at: datetime
    updated_at: datetime
