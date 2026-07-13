# app\services\interview_rubric_service.py

"""Per-criterion rubric scoring ответов на practice-кейсы (Этап 9.F).

Детерминированный scoring **без AI** (``app/domain/interview_rubric_scoring.py``),
персистентность попыток (``interview_prep_answer_attempts``, зашифрованный
``answer_text`` — ФЗ-152 ст.19), cross-session progress (backward-looking
snapshot, без прогнозов). Ownership — единый 404 через
``vacancy_repo.get_by_id(user_id=)``. ``require_data_processing_consent`` (без AI).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.case_prep import STABLE_CASE_TYPES
from app.domain.interview_rubric_scoring import (
    RUBRIC_VERSION,
    build_cross_session_progress,
    score_answer_against_rubric,
)
from app.repositories.interview_prep_answer_attempt_repository import (
    InterviewPrepAnswerAttemptRepository,
)
from app.repositories.vacancy_repository import VacancyRepository


class InterviewRubricService:
    """Submit/list/progress для per-criterion rubric scoring ответов."""

    def __init__(
        self,
        *,
        vacancy_repo: VacancyRepository | None = None,
        attempt_repo: InterviewPrepAnswerAttemptRepository | None = None,
    ) -> None:
        self.vacancy_repo = vacancy_repo or VacancyRepository()
        self.attempt_repo = attempt_repo or InterviewPrepAnswerAttemptRepository()

    async def _ensure_vacancy_owned(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
    ) -> None:
        vacancy = await self.vacancy_repo.get_by_id(
            session, vacancy_id, user_id=user_id
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

    async def submit_answer(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        case_id: str,
        case_type: str,
        answer_text: str,
    ) -> dict[str, Any]:
        await self._ensure_vacancy_owned(
            session, user_id=user_id, vacancy_id=vacancy_id
        )

        if case_type not in STABLE_CASE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unsupported case_type '{case_type}'",
            )
        if not (answer_text or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="answer_text must not be empty",
            )

        report = score_answer_against_rubric(case_type, answer_text)
        attempt = await self.attempt_repo.create(
            session,
            user_id=user_id,
            vacancy_id=vacancy_id,
            case_id=case_id,
            case_type=case_type,
            answer_text=answer_text,
            criterion_scores_json=[c.as_dict() for c in report.criterion_scores],
            overall_score=report.overall_score,
            grade=report.grade,
            feedback_json={
                "strengths": list(report.feedback.get("strengths", [])),
                "improvements": list(report.feedback.get("improvements", [])),
                "issues": list(report.feedback.get("issues", [])),
            },
            rubric_version=RUBRIC_VERSION,
        )

        result = report.as_dict()
        result["attempt_id"] = str(attempt.id)
        result["case_id"] = case_id
        result["case_type"] = case_type
        result["created_at"] = attempt.created_at
        return result

    async def list_attempts(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        case_id: str,
    ) -> list[dict[str, Any]]:
        await self._ensure_vacancy_owned(
            session, user_id=user_id, vacancy_id=vacancy_id
        )
        attempts = await self.attempt_repo.list_by_user_vacancy_case(
            session, user_id=user_id, vacancy_id=vacancy_id, case_id=case_id
        )
        return [
            {
                "attempt_id": str(a.id),
                "case_id": a.case_id,
                "case_type": a.case_type,
                "overall_score": float(a.overall_score),
                "grade": a.grade,
                "created_at": a.created_at,
            }
            for a in attempts
        ]

    async def build_progress(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        case_id: str,
    ) -> dict[str, Any]:
        await self._ensure_vacancy_owned(
            session, user_id=user_id, vacancy_id=vacancy_id
        )
        attempts = await self.attempt_repo.list_by_user_vacancy_case(
            session, user_id=user_id, vacancy_id=vacancy_id, case_id=case_id
        )
        snapshots = [
            {
                "overall_score": float(a.overall_score),
                "criterion_scores_json": list(a.criterion_scores_json or []),
            }
            for a in attempts
        ]
        progress = build_cross_session_progress(snapshots)
        progress["vacancy_id"] = str(vacancy_id)
        progress["case_id"] = case_id
        return progress