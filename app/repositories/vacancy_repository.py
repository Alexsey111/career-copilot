# app\repositories\vacancy_repository.py

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, or_, text, func
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
        embedding: list[float] | None = None,
        salary_from: float | None = None,
        salary_to: float | None = None,
        salary_currency: str | None = None,
        employment_type: str | None = None,
        experience_level: str | None = None,
    ) -> Vacancy:
        vacancy = Vacancy(
            user_id=user_id,
            source=source,
            source_url=source_url,
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            salary_from=salary_from,
            salary_to=salary_to,
            salary_currency=salary_currency,
            employment_type=employment_type,
            experience_level=experience_level,
            description_raw=description_raw,
            normalized_json=normalized_json,
            embedding=embedding,
        )
        session.add(vacancy)
        await session.flush()
        return vacancy

    async def get_by_id(
        self,
        session: AsyncSession,
        vacancy_id: UUID,
        *,
        user_id: UUID,
    ) -> Vacancy | None:
        stmt = (
            select(Vacancy)
            .where(Vacancy.id == vacancy_id)
            .where(Vacancy.user_id == user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[Vacancy]:
        stmt = (
            select(Vacancy)
            .where(Vacancy.user_id == user_id)
            .order_by(Vacancy.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        query: str | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        experience_level: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Vacancy]:
        stmt = select(Vacancy).where(Vacancy.user_id == user_id)

        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Vacancy.title.ilike(pattern),
                    Vacancy.company.ilike(pattern),
                    Vacancy.description_raw.ilike(pattern),
                )
            )
        if location:
            stmt = stmt.where(Vacancy.location.ilike(f"%{location}%"))
        if employment_type:
            stmt = stmt.where(Vacancy.employment_type == employment_type)
        if experience_level:
            stmt = stmt.where(Vacancy.experience_level == experience_level)
        if salary_min is not None:
            stmt = stmt.where(Vacancy.salary_to >= salary_min)
        if salary_max is not None:
            stmt = stmt.where(Vacancy.salary_from <= salary_max)

        stmt = stmt.order_by(Vacancy.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def semantic_search(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        query_embedding: list[float],
        query_text: str = "",
        location: str | None = None,
        employment_type: str | None = None,
        experience_level: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        similarity_threshold: float = 0.3,
        limit: int = 20,
    ) -> list[tuple[Vacancy, float]]:
        count_stmt = select(func.count()).select_from(Vacancy).where(
            Vacancy.user_id == user_id, Vacancy.embedding.isnot(None)
        )
        count_result = await session.execute(count_stmt)
        embedding_count = count_result.scalar()

        if embedding_count == 0:
            return await self._text_fallback_search(
                session,
                user_id=user_id,
                query=query_text,
                location=location,
                limit=limit,
            )

        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        where_clauses = ["v.user_id = :user_id", "v.embedding IS NOT NULL"]
        params: dict[str, Any] = {
            "user_id": user_id,
            "embedding": embedding_str,
            "threshold": similarity_threshold,
            "limit": limit,
        }

        if location:
            where_clauses.append("v.location ILIKE :location")
            params["location"] = f"%{location}%"
        if employment_type:
            where_clauses.append("v.employment_type = :employment_type")
            params["employment_type"] = employment_type
        if experience_level:
            where_clauses.append("v.experience_level = :experience_level")
            params["experience_level"] = experience_level
        if salary_min is not None:
            where_clauses.append("v.salary_to >= :salary_min")
            params["salary_min"] = salary_min
        if salary_max is not None:
            where_clauses.append("v.salary_from <= :salary_max")
            params["salary_max"] = salary_max

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT v.*, 1 - (v.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM vacancies v
            WHERE {where_sql}
              AND 1 - (v.embedding <=> CAST(:embedding AS vector)) >= :threshold
            ORDER BY v.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        result = await session.execute(sql, params)
        rows = result.mappings().all()

        vacancies_with_score: list[tuple[Vacancy, float]] = []
        for row in rows:
            vacancy = await session.get(Vacancy, row["id"])
            if vacancy is not None:
                vacancies_with_score.append((vacancy, float(row["similarity"])))

        # Semantic может вернуть пусто, если cosine-сходство ниже порога
        # (модель embedding даёт низкие absolute-значения cosine, и дефолтный
        # threshold 0.3 отсекает даже релевантные вакансии). В этом случае
        # честнее показать текстовый fallback, чем пустой список — иначе для
        # юзера поиск выглядит «не работающим».
        if not vacancies_with_score and query_text:
            return await self._text_fallback_search(
                session,
                user_id=user_id,
                query=query_text,
                location=location,
                limit=limit,
            )

        return vacancies_with_score

    async def _text_fallback_search(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        query: str = "",
        location: str | None = None,
        limit: int = 20,
    ) -> list[tuple[Vacancy, float]]:
        stmt = select(Vacancy).where(Vacancy.user_id == user_id)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Vacancy.title.ilike(pattern),
                    Vacancy.company.ilike(pattern),
                    Vacancy.description_raw.ilike(pattern),
                )
            )
        if location:
            stmt = stmt.where(Vacancy.location.ilike(f"%{location}%"))
        stmt = stmt.order_by(Vacancy.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        vacancies = list(result.scalars().all())
        return [(v, 0.0) for v in vacancies]

    async def update_embedding(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
        embedding: list[float],
    ) -> Vacancy | None:
        vacancy = await self.get_by_id(session, vacancy_id, user_id=user_id)
        if vacancy is None:
            return None
        vacancy.embedding = embedding
        await session.flush()
        return vacancy
