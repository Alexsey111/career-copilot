# app\domain\parse_diagnostics.py

"""Доменные модели отчёта «как видит парсер» (Этап 8 — ATS-диагностика + anti-hack).

Отчёт описывает, как машинный парсер видит загруженное резюме: какие блоки
(секции) распознаны и в каком порядке, какие фрагменты «потеряны» (orphan-строки
вне распознанных секций), структурные предупреждения (таблицы/колонки/длинные
строки/скан-риск) и находки скрытого/невидимого текста (white-on-white,
tiny-font, zero-width, docx-vanish) — вектор «взлома» ATS-ранжирования.

См. «первоначальное исследование.md» стр. 16, 18, 39 и
`docs/document_quality_contract.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExtractedBlock:
    """Распознанная секция резюме (как её «видит» парсер)."""

    kind: str
    label: str
    line_start: int
    line_end: int
    char_count: int
    sample: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "char_count": self.char_count,
            "sample": self.sample,
        }


@dataclass(slots=True)
class LostBlock:
    """Фрагмент текста, не отнесённый ни к одной распознанной секции."""

    sample: str
    reason: str
    line_start: int
    line_end: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample": self.sample,
            "reason": self.reason,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


@dataclass(slots=True)
class StructuralWarning:
    code: str
    message: str
    severity: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(slots=True)
class HiddenTextFinding:
    """Находка скрытого/невидимого текста — вектор «взлома» ATS-ранжирования.

    kind:
      - ``white_on_white`` — текст цветом фона (PDF span color 0xFFFFFF / DOCX
        run color белый); высокая вероятность скрытого ключевого слова.
      - ``tiny_font`` — шрифт <2pt (PDF span size / DOCX run font size); почти
        невидимый, но индексируется парсером.
      - ``zero_width`` — zero-width/invisible Unicode (U+200B/200C/200D/FEFF/
        U+00AD/U+2060); может разделять ключевое слово для обхода анти-спам-фильтров
        либо, наоборот, быть легитимным — severity low.
      - ``docx_vanish`` — DOCX run с ``w:vanish`` (скрытый текст Word).
    """

    kind: str
    count: int
    sample: str
    severity: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "count": self.count,
            "sample": self.sample,
            "severity": self.severity,
        }


@dataclass(slots=True)
class FileMetadata:
    """Прочитанные метаданные файла (могут содержать PII / утечку автора)."""

    author: str | None = None
    title: str | None = None
    producer: str | None = None
    created: str | None = None
    creator_tool: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "author": self.author,
            "title": self.title,
            "producer": self.producer,
            "created": self.created,
            "creator_tool": self.creator_tool,
        }

    def has_exposure(self) -> bool:
        """True, если любое поле метаданных содержит непустое значение."""
        return any(
            value
            for value in (
                self.author,
                self.title,
                self.producer,
                self.created,
                self.creator_tool,
            )
        )


@dataclass(slots=True)
class ParseDiagnosticsReport:
    detected_format: str
    stats: dict[str, Any] = field(default_factory=dict)
    extracted_blocks: list[ExtractedBlock] = field(default_factory=list)
    block_order: list[str] = field(default_factory=list)
    lost_blocks: list[LostBlock] = field(default_factory=list)
    structural_warnings: list[StructuralWarning] = field(default_factory=list)
    hidden_text_findings: list[HiddenTextFinding] = field(default_factory=list)
    file_metadata: FileMetadata = field(default_factory=FileMetadata)
    metadata_exposure_warning: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "detected_format": self.detected_format,
            "stats": self.stats,
            "extracted_blocks": [b.as_dict() for b in self.extracted_blocks],
            "block_order": list(self.block_order),
            "lost_blocks": [b.as_dict() for b in self.lost_blocks],
            "structural_warnings": [w.as_dict() for w in self.structural_warnings],
            "hidden_text_findings": [f.as_dict() for f in self.hidden_text_findings],
            "file_metadata": self.file_metadata.as_dict(),
            "metadata_exposure_warning": self.metadata_exposure_warning,
        }