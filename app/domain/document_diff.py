# app\domain\document_diff.py

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class SectionDiff:
    section: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentDiffResult:
    base_document_id: UUID
    target_document_id: UUID
    sections: list[SectionDiff] = field(default_factory=list)
