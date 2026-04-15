# app\repositories\candidate_profile_repository.py

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import CandidateProfile


class CandidateProfileRepository:
    async def get_by_user_id(
        self,
        session: AsyncSession,
        user_id,
    ) -> CandidateProfile | None:
        stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_related_by_user_id(
        self,
        session: AsyncSession,
        user_id,
    ) -> CandidateProfile | None:
        stmt = (
            select(CandidateProfile)
            .options(
                selectinload(CandidateProfile.experiences),
                selectinload(CandidateProfile.achievements),
            )
            .where(CandidateProfile.user_id == user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_empty(
        self,
        session: AsyncSession,
        *,
        user_id,
    ) -> CandidateProfile:
        profile = CandidateProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
        await session.refresh(profile)
        return profile