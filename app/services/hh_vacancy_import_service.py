# app\services\hh_vacancy_import_service.py

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings


class HHVacancyImportService:
    API_BASE_URL = "https://api.hh.ru"

    def extract_vacancy_id(self, source_url: str) -> str:
        match = re.search(r"/vacancy/(\d+)", source_url)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="HH API is unavailable: DNS/network error from backend container",
            ) from exc
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="HH API request timed out",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"HH API request failed: {exc.__class__.__name__}",
            ) from exc

        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HH vacancy not found",
            )

        if response.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "HH API отклонил запрос. "
                    "Используйте ручной импорт: вставьте текст вакансии в форму ниже."
                ),
            )

        if response.status_code >= 400:
            response_preview = response.text[:500]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"HH API returned HTTP {response.status_code}. "
                    f"Used HH-User-Agent: {hh_user_agent}. "
                    f"Response: {response_preview}"
                ),
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="HH API returned unexpected payload",
            )

        return payload

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

        if salary:
            description_parts.append(f"Зарплата: {salary}")

        if experience:
            description_parts.append(f"Опыт: {experience.get('name')}")

        if employment:
            description_parts.append(f"Тип занятости: {employment.get('name')}")

        if schedule:
            description_parts.append(f"График: {schedule.get('name')}")

        return {
            "source": "hh",
            "source_url": source_url,
            "external_id": str(payload.get("id") or ""),
            "title": str(payload.get("name") or "").strip() or "HH vacancy",
            "company": str(employer.get("name") or "").strip() or None,
            "location": str(area.get("name") or "").strip() or None,
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
