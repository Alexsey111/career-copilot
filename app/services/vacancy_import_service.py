# app\services\vacancy_import_service.py

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vacancy
from app.repositories.source_file_repository import SourceFileRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.hh_vacancy_import_service import HHVacancyImportService
from app.services.resume_parser_service import ResumeParserService
from app.services.storage_service import StorageService
from app.services.vacancy_text_extractors.contracts import (
    VacancyExtractionResult,
)
from app.services.vacancy_text_extractors.trafilatura_extractor import (
    TrafilaturaVacancyExtractor,
)
from app.services.embedding_service import EmbeddingService
from app.domain.vacancy_fields_extractor import VacancyFields, extract_vacancy_fields


MAX_VACANCY_TEXT_LENGTH = 120_000


class VacancyImportService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        hh_vacancy_import_service: HHVacancyImportService | None = None,
        source_file_repository: SourceFileRepository | None = None,
        storage_service: StorageService | None = None,
        text_parser_service: ResumeParserService | None = None,
    ) -> None:
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.hh_vacancy_import_service = (
            hh_vacancy_import_service or HHVacancyImportService()
        )
        self.source_file_repository = source_file_repository or SourceFileRepository()
        self.storage_service = storage_service or StorageService()
        self.text_parser_service = text_parser_service or ResumeParserService()
        self.extractor = TrafilaturaVacancyExtractor()
        self.embedding_service = EmbeddingService()

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
        salary_from: float | None = None,
        salary_to: float | None = None,
        salary_currency: str | None = None,
        employment_type: str | None = None,
        experience_level: str | None = None,
    ) -> Vacancy:
        final_description = (description_raw or "").strip()
        fetched_title: str | None = None
        extraction_result: VacancyExtractionResult | None = None
        normalized_source = source.strip().lower() or "manual"

        if not final_description:
            if not source_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="either description_raw or source_url must be provided",
                )
            if self._is_hh_vacancy_url(source_url):
                hh_payload = await self.hh_vacancy_import_service.fetch_vacancy(source_url)
                mapped_payload = self.hh_vacancy_import_service.map_to_import_payload(
                    hh_payload,
                    source_url=source_url,
                )
                fetched_title = mapped_payload.get("title")
                final_description = str(mapped_payload.get("description_raw") or "")
                normalized_source = "hh"
                if not title:
                    title = mapped_payload.get("title")
                if not company:
                    company = mapped_payload.get("company")
                if not location:
                    location = mapped_payload.get("location")
                if not external_id:
                    external_id = mapped_payload.get("external_id")
            else:
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

        # Ручной импорт текста: попытаемся детерминированно извлечь
        # структурированные поля (title/company/salary/опыт/занятость) из
        # шапки hh-вакансии, если они не переданы явно. Без этого карточка
        # вакансии показывала «-» в Компания/Локация/Зарплата.
        extracted = self._extract_fields_if_missing(
            text=final_description,
            title=title,
            company=company,
            location=location,
            salary_from=salary_from,
            salary_to=salary_to,
            salary_currency=salary_currency,
            employment_type=employment_type,
            experience_level=experience_level,
        )
        if not title:
            # title приоритетнее fetched_title, но extract_vacancy_title обычно
            # точнее «Untitled vacancy» для ручного текста.
            final_title = (extracted.title or fetched_title or "Untitled vacancy").strip()
        if not company:
            company = extracted.company
        if not location:
            location = extracted.location
        if salary_from is None:
            salary_from = extracted.salary_from
        if salary_to is None:
            salary_to = extracted.salary_to
        if not salary_currency:
            salary_currency = extracted.salary_currency
        if not employment_type:
            employment_type = extracted.employment_type
        if not experience_level:
            experience_level = extracted.experience_level

        embedding_text = f"{final_title} {final_description[:2000]}"
        embedding = self.embedding_service.embed_text(embedding_text)

        normalized_json = {
            "import_mode": "manual_text" if description_raw else "fetched_url",
            "raw_text_length": len(final_description),
            "fetched_title": fetched_title,
            "fields_extraction": (
                "vacancy_fields_extractor"
                if (description_raw and not source_url)
                else None
            ),
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
            source=normalized_source,
            source_url=source_url,
            external_id=external_id,
            title=final_title,
            company=(company or None),
            location=(location or None),
            description_raw=final_description,
            normalized_json=normalized_json,
            embedding=embedding,
            salary_from=salary_from,
            salary_to=salary_to,
            salary_currency=salary_currency,
            employment_type=employment_type,
            experience_level=experience_level,
        )

        await session.commit()
        await session.refresh(vacancy)
        return vacancy

    def _extract_fields_if_missing(
        self,
        *,
        text: str,
        title: str | None,
        company: str | None,
        location: str | None,
        salary_from: float | None,
        salary_to: float | None,
        salary_currency: str | None,
        employment_type: str | None,
        experience_level: str | None,
    ) -> VacancyFields:
        # Запускаем экстрактор, только если хоть одно поле не передано явно —
        # иначе нет смысла парсить текст.
        if all(
            value
            for value in (title, company, location, salary_from, salary_to, salary_currency, employment_type, experience_level)
        ):
            return VacancyFields()
        return extract_vacancy_fields(
            text,
            fallback_title=title or "",
        )

    async def import_vacancy_from_source_file(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source_file_id: UUID,
        title: str | None = None,
        company: str | None = None,
        location: str | None = None,
        source_url: str | None = None,
    ) -> Vacancy:
        source_file = await self.source_file_repository.get_by_id(
            session,
            source_file_id,
            user_id=user_id,
        )
        if source_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="source file not found",
            )

        if source_file.file_kind != "vacancy":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source file is not a vacancy",
            )

        file_bytes = self.storage_service.download_bytes(
            storage_key=source_file.storage_key,
        )

        parsed = self.text_parser_service.parse(
            file_bytes=file_bytes,
            mime_type=source_file.mime_type,
            filename=source_file.original_name,
        )

        return await self.import_vacancy(
            session,
            user_id=user_id,
            source="file",
            source_url=source_url,
            external_id=None,
            title=title or Path(source_file.original_name).stem,
            company=company,
            location=location,
            description_raw=parsed.text,
        )

    def _is_hh_vacancy_url(self, source_url: str) -> bool:
        normalized_url = source_url.strip().lower()
        return "hh.ru" in normalized_url and "/vacancy/" in normalized_url

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
