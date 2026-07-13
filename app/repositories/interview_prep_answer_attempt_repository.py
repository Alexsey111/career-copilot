# app\repositories\interview_prep_answer_attempt_repository.py

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InterviewPrepAnswerAttempt


class InterviewPrepAnswerAttemptRepository:
    """Репозиторий попыток ответов на practice-кейсы (Этап 9.F).

    Все методы с ``user_id`` (defense in depth — ownership проверяется в сервисе
    через vacancy_repo, но и select фильтрует по user_id). Образец:
    ``interview_prep_session_repository.py``.
    """

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        case_id: str,
        case_type: str,
        answer_text: str,
        criterion_scores_json: list[dict],
        overall_score: float,
        grade: str,
        feedback_json: dict,
        rubric_version: str,
    ) -> InterviewPrepAnswerAttempt:
        attempt = InterviewPrepAnswerAttempt(
            user_id=user_id,
            vacancy_id=vacancy_id,
            case_id=case_id,
            case_type=case_type,
            answer_text=answer_text,
            criterion_scores_json=criterion_scores_json,
            overall_score=overall_score,
            grade=grade,
            feedback_json=feedback_json,
            rubric_version=rubric_version,
        )
        session.add(attempt)
        await session.flush()
        await session.refresh(attempt)
        return attempt

    async def get_by_id(
        self,
        session: AsyncSession,
        attempt_id: UUID,
        *,
        user_id: UUID,
    ) -> InterviewPrepAnswerAttempt | None:
        stmt = (
            select(InterviewPrepAnswerAttempt)
            .where(InterviewPrepAnswerAttempt.id == attempt_id)
            .where(InterviewPrepAnswerAttempt.user_id == user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_vacancy_case(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        case_id: str,
    ) -> list[InterviewPrepAnswerAttempt]:
        stmt = (
            select(InterviewPrepAnswerAttempt)
            .where(InterviewPrepAnswerAttempt.user_id == user_id)
            .where(InterviewPrepAnswerAttempt.vacancy_id == vacancy_id)
            .where(InterviewPrepAnswerAttempt.case_id == case_id)
            .order_by(InterviewPrepAnswerAttempt.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())