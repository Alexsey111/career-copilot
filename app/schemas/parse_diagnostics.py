# app\schemas\parse_diagnostics.py

"""Схемы эндпоинта диагностики парсинга (Этап 8)."""

from __future__ import annotations

from typing import Any

from uuid import UUID

from pydantic import Field

from app.schemas.base import StrictBaseModel


class ParseDiagnosticsRequest(StrictBaseModel):
    source_file_id: UUID


class ExtractedBlockItem(StrictBaseModel):
    kind: str
    label: str
    line_start: int
    line_end: int
    char_count: int
    sample: str


class LostBlockItem(StrictBaseModel):
    sample: str
    reason: str
    line_start: int
    line_end: int


class StructuralWarningItem(StrictBaseModel):
    code: str
    message: str
    severity: str


class HiddenTextFindingItem(StrictBaseModel):
    kind: str
    count: int
    sample: str
    severity: str


class FileMetadataItem(StrictBaseModel):
    author: str | None = None
    title: str | None = None
    producer: str | None = None
    created: str | None = None
    creator_tool: str | None = None


class ParseDiagnosticsResponse(StrictBaseModel):
    detected_format: str
    stats: dict[str, Any] = Field(default_factory=dict)
    extracted_blocks: list[ExtractedBlockItem] = Field(default_factory=list)
    block_order: list[str] = Field(default_factory=list)
    lost_blocks: list[LostBlockItem] = Field(default_factory=list)
    structural_warnings: list[StructuralWarningItem] = Field(default_factory=list)
    hidden_text_findings: list[HiddenTextFindingItem] = Field(default_factory=list)
    file_metadata: FileMetadataItem = Field(default_factory=FileMetadataItem)
    metadata_exposure_warning: bool = False