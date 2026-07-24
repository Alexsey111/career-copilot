"""Pydantic-схемы для ``/profile/resumes`` (листинг + reuse ранее загруженных).

Дополняет ``app.schemas.source_file.SourceFileRead`` сведениями о последнем
``FileExtraction`` (для preview) и lifecycle-флагами.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResumeListItem(BaseModel):
    """Один элемент ``GET /profile/resumes``.

    Не включает ``storage_key`` (security — клиенту он не нужен) и полный
    ``extracted_text`` (ПДн, EncryptedText). Возвращается ``text_preview``
    первые 500 символов — для UI подтверждения «это то самое резюме».
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_kind: str
    original_name: str
    mime_type: str | None
    size_bytes: int | None
    content_sha256: str | None = None
    lifecycle_status: str
    lineage_group_id: UUID | None = None
    superseded_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    # Из последнего FileExtraction
    latest_extraction_id: UUID | None = None
    latest_extraction_status: str | None = None
    text_preview: str | None = Field(
        default=None,
        max_length=500,
        description="Первые 500 символов extracted_text (расшифрован на бэке).",
    )
    detected_format: str | None = None
    extracted_at: datetime | None = None

    # Удобные флаги
    is_active: bool = True
    is_reusable: bool = True


class ResumeListResponse(BaseModel):
    items: list[ResumeListItem]
    total: int
    active_source_file_id: UUID | None = None


class ResumeReuseResponse(BaseModel):
    """Ответ ``POST /profile/resumes/{source_file_id}/reuse``.

    Сигнатура совпадает с ``ResumeImportResponse`` (тот же контракт:
    ``profile_id`` + ``extraction_id``), но НЕ включает повторный парсинг,
    если ``reparse=false`` — отдаём уже существующий ``extraction_id``.
    """

    profile_id: UUID | None = None
    source_file_id: UUID
    extraction_id: UUID | None = None
    status: str
    detected_format: str | None = None
    text_length: int | None = None
    text_preview: str | None = Field(default=None, max_length=1000)
    reparse_performed: bool
    reused: bool
    created_at: datetime
