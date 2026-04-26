# app\repositories\vacancy_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vacancy


class VacancyRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source: str,
        source_url: str | None,
        external_id: str | None,
        title: str,
        company: str | None,
        location: str | None,
        description_raw: str,
        normalized_json: dict,
    ) -> Vacancy:
        vacancy = Vacancy(
            user_id=user_id,
            source=source,
            source_url=source_url,
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            description_raw=description_raw,
            normalized_json=normalized_json,
        )
        session.add(vacancy)
        await session.flush()
        return vacancy

    async def get_by_id(self, session: AsyncSession, vacancy_id: UUID) -> Vacancy | None:
        stmt = select(Vacancy).where(Vacancy.id == vacancy_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
