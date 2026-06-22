# app\repositories\interview_prep_session_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InterviewPrepSession


class InterviewPrepSessionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        application_id: UUID,
        prep_status: str,
        readiness_score: int | None,
        competency_map_json: dict,
        question_set_json: list[dict],
        evidence_links_json: list[dict],
        weak_areas_json: list[dict],
        readiness_json: dict,
    ) -> InterviewPrepSession:
        interview_prep_session = InterviewPrepSession(
            user_id=user_id,
            vacancy_id=vacancy_id,
            application_id=application_id,
            prep_status=prep_status,
            readiness_score=readiness_score,
            competency_map_json=competency_map_json,
            question_set_json=question_set_json,
            evidence_links_json=evidence_links_json,
            weak_areas_json=weak_areas_json,
            readiness_json=readiness_json,
        )
        session.add(interview_prep_session)
        await session.flush()
        await session.refresh(interview_prep_session)
        return interview_prep_session

    async def get_by_id(
        self,
        session: AsyncSession,
        prep_session_id: UUID,
        *,
        user_id: UUID,
    ) -> InterviewPrepSession | None:
        stmt = (
            select(InterviewPrepSession)
            .where(InterviewPrepSession.id == prep_session_id)
            .where(InterviewPrepSession.user_id == user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_application_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        application_id: UUID,
    ) -> InterviewPrepSession | None:
        stmt = (
            select(InterviewPrepSession)
            .where(InterviewPrepSession.user_id == user_id)
            .where(InterviewPrepSession.application_id == application_id)
            .order_by(InterviewPrepSession.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[InterviewPrepSession]:
        stmt = (
            select(InterviewPrepSession)
            .where(InterviewPrepSession.user_id == user_id)
            .order_by(InterviewPrepSession.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_application_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        application_id: UUID,
    ) -> int:
        stmt = delete(InterviewPrepSession).where(
            InterviewPrepSession.user_id == user_id,
            InterviewPrepSession.application_id == application_id,
        )
        result = await session.execute(stmt)
        return int(result.rowcount or 0)

    async def delete_by_ids(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        session_ids: list[UUID],
    ) -> int:
        if not session_ids:
            return 0

        stmt = delete(InterviewPrepSession).where(
            InterviewPrepSession.user_id == user_id,
            InterviewPrepSession.id.in_(session_ids),
        )
        result = await session.execute(stmt)
        return int(result.rowcount or 0)
