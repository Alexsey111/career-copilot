# app\services\vacancy_import_service.py

from __future__ import annotations

import re
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vacancy
from app.repositories.vacancy_repository import VacancyRepository
from app.services.vacancy_text_extractors.contracts import (
    VacancyExtractionResult,
)
from app.services.vacancy_text_extractors.trafilatura_extractor import (
    TrafilaturaVacancyExtractor,
)


MAX_VACANCY_TEXT_LENGTH = 120_000


class VacancyImportService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
    ) -> None:
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.extractor = TrafilaturaVacancyExtractor()

    async def import_vacancy(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source: str,
        source_url: str | None,
        external_id: str | None,
        title: str | None,
        company: str | None,
        location: str | None,
        description_raw: str | None,
    ) -> Vacancy:
        final_description = (description_raw or "").strip()
        fetched_title: str | None = None
        extraction_result: VacancyExtractionResult | None = None

        if not final_description:
            if not source_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="either description_raw or source_url must be provided",
                )
            extraction_result = await self._fetch_url_text(source_url)
            fetched_title = extraction_result.title
            final_description = extraction_result.text

        if not final_description:
            raise HTTPException(
                status_code=422,
                detail="could not import vacancy text",
            )

        final_description = self._normalize_text(final_description)
        final_description = self._truncate_text(final_description)
        self._ensure_text_is_not_corrupted(final_description)

        final_title = (title or fetched_title or "Untitled vacancy").strip()

        normalized_json = {
            "import_mode": "manual_text" if description_raw else "fetched_url",
            "raw_text_length": len(final_description),
            "fetched_title": fetched_title,
            "extractor": (
                extraction_result.extractor if extraction_result else None
            ),
            "extraction_method": (
                extraction_result.extraction_method
                if extraction_result
                else None
            ),
        }

        vacancy = await self.vacancy_repository.create(
            session,
            user_id=user_id,
            source=source.strip().lower() or "manual",
            source_url=source_url,
            external_id=external_id,
            title=final_title,
            company=(company or None),
            location=(location or None),
            description_raw=final_description,
            normalized_json=normalized_json,
        )

        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    async def _fetch_url_text(
        self,
        source_url: str,
    ) -> VacancyExtractionResult:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(
                    source_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0 Safari/537.36"
                        )
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"could not fetch vacancy url: {exc}",
            ) from exc

        result = await self.extractor.extract(
            url=source_url,
            html=response.text,
        )

        return result

    def _normalize_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        non_empty = [line for line in lines if line]
        normalized = "\n".join(non_empty)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _truncate_text(self, text: str) -> str:
        if len(text) <= MAX_VACANCY_TEXT_LENGTH:
            return text

        return text[:MAX_VACANCY_TEXT_LENGTH].strip()

    def _ensure_text_is_not_corrupted(self, text: str) -> None:
        if not self._looks_like_corrupted_text(text):
            return

        raise HTTPException(
            status_code=422,
            detail=(
                "vacancy text looks corrupted; check client encoding and send JSON as UTF-8"
            ),
        )

    def _looks_like_corrupted_text(self, text: str) -> bool:
        if not text:
            return False

        replacement_char_count = text.count("�")
        if replacement_char_count > 0:
            return True

        question_runs = re.findall(r"\?{4,}", text)
        question_mark_count = sum(len(item) for item in question_runs)

        if question_mark_count == 0:
            return False

        cyrillic_count = sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")

        # Typical broken Russian headings become:
        # "??????????" and "????? ??????"
        if question_mark_count >= 8 and cyrillic_count == 0:
            return True

        return False
