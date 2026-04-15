# app\repositories\vacancy_analysis_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VacancyAnalysis


class VacancyAnalysisRepository:
    async def replace_for_vacancy(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        must_have_json: list[dict],
        nice_to_have_json: list[dict],
        keywords_json: list[str],
        gaps_json: list[dict],
        strengths_json: list[dict],
        match_score: int | None,
        analysis_version: str,
    ) -> VacancyAnalysis:
        await session.execute(
            delete(VacancyAnalysis).where(VacancyAnalysis.vacancy_id == vacancy_id)
        )

        analysis = VacancyAnalysis(
            vacancy_id=vacancy_id,
            must_have_json=must_have_json,
            nice_to_have_json=nice_to_have_json,
            keywords_json=keywords_json,
            gaps_json=gaps_json,
            strengths_json=strengths_json,
            match_score=match_score,
            analysis_version=analysis_version,
        )
        session.add(analysis)
        await session.flush()
        await session.refresh(analysis)
        return analysis

    async def get_latest_for_vacancy(
        self,
        session: AsyncSession,
        vacancy_id: UUID,
    ) -> VacancyAnalysis | None:
        stmt = (
            select(VacancyAnalysis)
            .where(VacancyAnalysis.vacancy_id == vacancy_id)
            .order_by(VacancyAnalysis.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()