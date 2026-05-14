"""Repository for persistent review workflow analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_workflow import (
    ReviewActionRecord,
    ReviewOutcomeRecord,
    ReviewSessionRecord,
)


@dataclass
class ReviewWorkflowMetricsAggregate:
    """Aggregated metrics for human review workflow."""

    total_sessions: int
    completed_sessions: int
    approved_sessions: int
    review_required_sessions: int
    average_review_duration_ms: float
    average_actions_per_session: float

    @property
    def approval_rate(self) -> float:
        return self.approved_sessions / self.completed_sessions if self.completed_sessions > 0 else 0.0

    @property
    def review_required_rate(self) -> float:
        return self.review_required_sessions / self.total_sessions if self.total_sessions > 0 else 0.0

    @property
    def completion_rate(self) -> float:
        return self.completed_sessions / self.total_sessions if self.total_sessions > 0 else 0.0


class ReviewWorkflowRepository:
    """SQLAlchemy repository for review workflow persistence."""

    async def create_session(
        self,
        session: AsyncSession,
        *,
        session_id: str,
        document_id: UUID,
        user_id: UUID,
        started_at: datetime,
        review_required: bool = True,
        status: str = "review_required",
        pipeline_execution_id: UUID | None = None,
        reviewer_id: UUID | None = None,
        review_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReviewSessionRecord:
        record = ReviewSessionRecord(
            session_id=session_id,
            pipeline_execution_id=pipeline_execution_id,
            document_id=document_id,
            user_id=user_id,
            reviewer_id=reviewer_id,
            status=status,
            review_required=review_required,
            review_reason=review_reason,
            started_at=started_at,
            metadata_json=metadata or {},
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        return record

    async def get_by_session_id(
        self,
        session: AsyncSession,
        session_id: str,
    ) -> ReviewSessionRecord | None:
        stmt = select(ReviewSessionRecord).where(ReviewSessionRecord.session_id == session_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_session(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        user_id: UUID,
    ) -> ReviewSessionRecord | None:
        stmt = (
            select(ReviewSessionRecord)
            .where(ReviewSessionRecord.document_id == document_id)
            .where(ReviewSessionRecord.user_id == user_id)
            .where(ReviewSessionRecord.completed_at.is_(None))
            .order_by(ReviewSessionRecord.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_action(
        self,
        session: AsyncSession,
        *,
        review_session_id: UUID,
        action_type: str,
        target_type: str | None = None,
        target_id: str | None = None,
        action_payload: dict[str, Any] | None = None,
    ) -> ReviewActionRecord:
        record = ReviewActionRecord(
            review_session_id=review_session_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            action_payload_json=action_payload or {},
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        return record

    async def record_outcome(
        self,
        session: AsyncSession,
        *,
        review_session_id: UUID,
        outcome_status: str,
        approved: bool,
        outcome_payload: dict[str, Any] | None = None,
    ) -> ReviewOutcomeRecord:
        record = ReviewOutcomeRecord(
            review_session_id=review_session_id,
            outcome_status=outcome_status,
            approved=approved,
            outcome_payload_json=outcome_payload or {},
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        return record

    async def complete_session(
        self,
        session: AsyncSession,
        *,
        review_session_id: UUID,
        completed_at: datetime,
        final_status: str,
        reviewer_id: UUID | None = None,
    ) -> ReviewSessionRecord | None:
        record = await self._get_by_id(session, review_session_id)
        if record is None:
            return None

        record.completed_at = completed_at
        record.review_duration_ms = int((completed_at - record.started_at).total_seconds() * 1000)
        record.final_status = final_status
        record.status = final_status
        if reviewer_id is not None:
            record.reviewer_id = reviewer_id

        await session.flush()
        await session.refresh(record)
        return record

    async def get_review_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> ReviewWorkflowMetricsAggregate:
        actions_subquery = (
            select(
                ReviewActionRecord.review_session_id.label("review_session_id"),
                func.count(ReviewActionRecord.id).label("action_count"),
            )
            .group_by(ReviewActionRecord.review_session_id)
            .subquery()
        )

        stmt = select(
            func.count(ReviewSessionRecord.id).label("total_sessions"),
            func.sum(case((ReviewSessionRecord.completed_at.isnot(None), 1), else_=0)).label("completed_sessions"),
            func.sum(case((ReviewSessionRecord.review_required.is_(True), 1), else_=0)).label("review_required_sessions"),
            func.sum(case((ReviewOutcomeRecord.outcome_status == "approved", 1), else_=0)).label("approved_sessions"),
            func.coalesce(func.avg(ReviewSessionRecord.review_duration_ms), 0.0).label("avg_duration"),
            func.coalesce(func.avg(actions_subquery.c.action_count), 0.0).label("avg_actions"),
        ).select_from(
            ReviewSessionRecord
        ).outerjoin(
            ReviewOutcomeRecord, ReviewOutcomeRecord.review_session_id == ReviewSessionRecord.id
        ).outerjoin(
            actions_subquery, actions_subquery.c.review_session_id == ReviewSessionRecord.id
        )

        if start_time is not None:
            stmt = stmt.where(ReviewSessionRecord.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(ReviewSessionRecord.created_at <= end_time)

        row = (await session.execute(stmt)).one()
        return ReviewWorkflowMetricsAggregate(
            total_sessions=row.total_sessions or 0,
            completed_sessions=row.completed_sessions or 0,
            approved_sessions=row.approved_sessions or 0,
            review_required_sessions=row.review_required_sessions or 0,
            average_review_duration_ms=row.avg_duration or 0.0,
            average_actions_per_session=row.avg_actions or 0.0,
        )

    async def _get_by_id(
        self,
        session: AsyncSession,
        review_session_id: UUID,
    ) -> ReviewSessionRecord | None:
        stmt = select(ReviewSessionRecord).where(ReviewSessionRecord.id == review_session_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
