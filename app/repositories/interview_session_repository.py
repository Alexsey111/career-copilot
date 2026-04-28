# app\repositories\interview_session_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InterviewSession, Vacancy


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

    async def list_dashboard_by_user_id(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> list[dict]:
        stmt = (
            select(
                InterviewSession,
                Vacancy.title,
                Vacancy.company,
                Vacancy.location,
            )
            .outerjoin(Vacancy, InterviewSession.vacancy_id == Vacancy.id)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.updated_at.desc())
        )

        result = await session.execute(stmt)

        items: list[dict] = []

        for interview_session, vacancy_title, vacancy_company, vacancy_location in result.all():
            score = interview_session.score_json or {}
            question_set = interview_session.question_set_json or []
            answers = interview_session.answers_json or []

            readiness_score = score.get("readiness_score")
            if readiness_score is not None:
                readiness_score = int(readiness_score)

            items.append(
                {
                    "id": interview_session.id,
                    "vacancy_id": interview_session.vacancy_id,
                    "vacancy_title": vacancy_title,
                    "vacancy_company": vacancy_company,
                    "vacancy_location": vacancy_location,
                    "session_type": interview_session.session_type,
                    "status": interview_session.status,
                    "question_count": int(score.get("question_count") or len(question_set)),
                    "answered_count": int(score.get("answered_count") or len(answers)),
                    "unanswered_count": int(score.get("unanswered_count") or 0),
                    "warning_count": int(score.get("warning_count") or 0),
                    "readiness_score": readiness_score,
                    "created_at": interview_session.created_at,
                    "updated_at": interview_session.updated_at,
                }
            )

        return items

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
