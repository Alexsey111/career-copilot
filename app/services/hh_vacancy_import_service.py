# app\services\hh_vacancy_import_service.py

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, status

from app.core.config import get_settings


class HHVacancyImportService:
    API_BASE_URL = "https://api.hh.ru"
    BROWSER_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )

    def extract_vacancy_id(self, source_url: str) -> str:
        match = re.search(r"/vacancy/(\d+)", source_url)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="could not extract HH vacancy id from source_url",
            )
        return match.group(1)

    async def fetch_vacancy(
        self,
        source_url: str,
        *,
        contact_email: str | None = None,
    ) -> dict[str, Any]:
        vacancy_id = self.extract_vacancy_id(source_url)
        settings = get_settings()
        hh_user_agent = settings.hh_user_agent

        if contact_email:
            hh_user_agent = f"career-copilot/0.1 {contact_email}"

        api_error: HTTPException | None = None
        try:
            async with httpx.AsyncClient(
                base_url=self.API_BASE_URL,
                timeout=20.0,
                headers={
                    "HH-User-Agent": hh_user_agent,
                },
            ) as client:
                response = await client.get(f"/vacancies/{vacancy_id}")
        except httpx.ConnectError as exc:
            api_error = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="HH API is unavailable: DNS/network error from backend container",
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
                cause=exc,
            )
        except httpx.TimeoutException as exc:
            api_error = HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="HH API request timed out",
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
                cause=exc,
            )
        except httpx.RequestError as exc:
            api_error = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"HH API request failed: {exc.__class__.__name__}",
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
                cause=exc,
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HH vacancy not found",
            )

        if response.status_code == 403:
            api_error = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "HH API отклонил запрос. "
                    "Используйте ручной импорт: вставьте текст вакансии в форму ниже."
                ),
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
            )

        if response.status_code >= 400:
            response_preview = response.text[:500]
            api_error = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"HH API returned HTTP {response.status_code}. "
                    f"Used HH-User-Agent: {hh_user_agent}. "
                    f"Response: {response_preview}"
                ),
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            api_error = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="HH API returned invalid JSON",
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
                cause=exc,
            )
        if not isinstance(payload, dict):
            api_error = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="HH API returned unexpected payload",
            )
            return await self._fetch_vacancy_page_or_raise(
                source_url,
                vacancy_id=vacancy_id,
                fallback_error=api_error,
            )

        return payload

    async def _fetch_vacancy_page_or_raise(
        self,
        source_url: str,
        *,
        vacancy_id: str,
        fallback_error: HTTPException,
        cause: Exception | None = None,
    ) -> dict[str, Any]:
        try:
            return await self._fetch_vacancy_page(source_url, vacancy_id=vacancy_id)
        except Exception as exc:
            if cause is not None:
                raise fallback_error from cause
            raise fallback_error from exc

    async def _fetch_vacancy_page(self, source_url: str, *, vacancy_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(
                source_url,
                headers={
                    "User-Agent": self.BROWSER_USER_AGENT,
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"HH vacancy page returned HTTP {response.status_code}",
            )

        extracted = self._extract_page_payload(
            response.text,
            vacancy_id=vacancy_id,
            source_url=source_url,
        )
        if not str(extracted.get("description") or "").strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="HH vacancy page did not contain readable vacancy text",
            )
        return extracted

    def _extract_page_payload(
        self,
        html: str,
        *,
        vacancy_id: str,
        source_url: str,
    ) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = self._first_text(
            soup,
            [
                '[data-qa="vacancy-title"]',
                "h1",
                "title",
            ],
        )
        description = self._first_html(
            soup,
            [
                '[data-qa="vacancy-description"]',
                ".vacancy-description",
                "main",
                "body",
            ],
        )
        employer = self._first_text(
            soup,
            [
                '[data-qa="vacancy-company-name"]',
                '[data-qa="bloko-header-2"]',
                ".vacancy-company-name",
            ],
        )
        area = self._first_text(
            soup,
            [
                '[data-qa="vacancy-view-location"]',
                '[data-qa="vacancy-view-raw-address"]',
            ],
        )

        return {
            "id": vacancy_id,
            "name": title or "HH vacancy",
            "alternate_url": source_url,
            "description": description or "",
            "employer": {"name": employer} if employer else {},
            "area": {"name": area} if area else {},
            "key_skills": [],
            "import_source": "hh_page_fallback",
        }

    def _first_text(self, soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            element = soup.select_one(selector)
            if element is None:
                continue
            text = element.get_text(" ", strip=True)
            if text:
                return text
        return None

    def _first_html(self, soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            element = soup.select_one(selector)
            if element is None:
                continue
            text = element.get_text(" ", strip=True)
            if text:
                return str(element)
        return None

    def map_to_import_payload(self, payload: dict[str, Any], *, source_url: str) -> dict[str, Any]:
        employer = payload.get("employer") or {}
        area = payload.get("area") or {}
        salary = payload.get("salary") or {}
        experience = payload.get("experience") or {}
        employment = payload.get("employment") or {}
        schedule = payload.get("schedule") or {}

        description = self._html_to_text(str(payload.get("description") or ""))
        key_skills = [
            str(item.get("name") or "").strip()
            for item in (payload.get("key_skills") or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]

        description_parts = [description]
        if key_skills:
            description_parts.append(
                "Ключевые навыки:\n" + "\n".join(f"- {skill}" for skill in key_skills)
            )

        # График отдельного поля не имеет — оставляем в описании. Зарплата/
        # опыт/занятость раньше тоже встраивались сюда как dict-repr
        # («Зарплата: {'from': 60000, ...}») — теперь они в отдельных полях
        # ниже, из description убраны (мусорный dict-repr ломал читаемость и
        # не парсился _extract_fields_if_missing).
        if schedule:
            description_parts.append(f"График: {schedule.get('name')}")

        return {
            "source": "hh",
            "source_url": source_url,
            "external_id": str(payload.get("id") or ""),
            "title": str(payload.get("name") or "").strip() or "HH vacancy",
            "company": str(employer.get("name") or "").strip() or None,
            "location": str(area.get("name") or "").strip() or None,
            "salary_from": salary.get("from") if isinstance(salary, dict) else None,
            "salary_to": salary.get("to") if isinstance(salary, dict) else None,
            "salary_currency": (
                str(salary.get("currency") or "").strip() or None
                if isinstance(salary, dict) else None
            ),
            "employment_type": (
                str(employment.get("name") or "").strip() or None
                if isinstance(employment, dict) else None
            ),
            "experience_level": (
                str(experience.get("name") or "").strip() or None
                if isinstance(experience, dict) else None
            ),
            "description_raw": "\n\n".join(part for part in description_parts if part),
        }

    def _html_to_text(self, value: str) -> str:
        text = value
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"(?i)</li\s*>", "\n", text)
        text = re.sub(r"(?i)<li\s*>", "- ", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
