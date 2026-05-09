# app\services\vacancy_text_extractors\contracts.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VacancyExtractionResult:
    title: str | None
    text: str
    extractor: str
    extraction_method: str
    content_length: int
    success: bool