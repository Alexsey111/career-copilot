# app\repositories\interview_session_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InterviewSession


class InterviewSessionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID | None,
        session_type: str,
        status: str,
        question_set_json: list[dict],
        answers_json: list[dict] | None = None,
        feedback_json: dict | None = None,
        score_json: dict | None = None,
    ) -> InterviewSession:
        interview_session = InterviewSession(
            user_id=user_id,
            vacancy_id=vacancy_id,
            session_type=session_type,
            status=status,
            question_set_json=question_set_json,
            answers_json=answers_json or [],
            feedback_json=feedback_json or {},
            score_json=score_json or {},
        )
        session.add(interview_session)
        await session.flush()
        await session.refresh(interview_session)
        return interview_session

    async def get_by_id(
        self,
        session: AsyncSession,
        session_id: UUID,
    ) -> InterviewSession | None:
        stmt = select(InterviewSession).where(InterviewSession.id == session_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_answers(
        self,
        session: AsyncSession,
        interview_session: InterviewSession,
        *,
        answers_json: list[dict],
        feedback_json: dict,
        score_json: dict,
        status: str,
    ) -> InterviewSession:
        interview_session.answers_json = answers_json
        interview_session.feedback_json = feedback_json
        interview_session.score_json = score_json
        interview_session.status = status

        await session.flush()
        await session.refresh(interview_session)
        return interview_session
