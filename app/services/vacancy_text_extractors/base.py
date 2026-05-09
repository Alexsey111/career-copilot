# app\services\vacancy_text_extractors\base.py

from __future__ import annotations

from app.services.vacancy_text_extractors.contracts import VacancyExtractionResult


class BaseVacancyExtractor:
    async def extract(
        self,
        *,
        url: str,
        html: str,
    ) -> VacancyExtractionResult:
        raise NotImplementedError
