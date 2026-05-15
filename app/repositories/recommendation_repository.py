"""Repository for persistent recommendations lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation import Recommendation, RecommendationLifecycleStatus


class RecommendationRepository:
    async def create_recommendation(
        self,
        session: AsyncSession,
        *,
        execution_id: UUID,
        document_id: UUID,
        category: str,
        message: str,
        estimated_score_improvement: float,
        confidence: float,
        status: RecommendationLifecycleStatus = RecommendationLifecycleStatus.PENDING,
    ) -> Recommendation:
        recommendation = Recommendation(
            execution_id=execution_id,
            document_id=document_id,
            category=category,
            message=message,
            estimated_score_improvement=estimated_score_improvement,
            confidence=confidence,
            status=status,
        )
        session.add(recommendation)
        await session.flush()
        await session.refresh(recommendation)
        return recommendation

    async def create_recommendations(
        self,
        session: AsyncSession,
        *,
        execution_id: UUID,
        document_id: UUID,
        recommendations: list[dict[str, Any]],
    ) -> list[Recommendation]:
        created: list[Recommendation] = []
        for recommendation_data in recommendations:
            created.append(
                await self.create_recommendation(
                    session,
                    execution_id=execution_id,
                    document_id=document_id,
                    category=str(recommendation_data.get("category", "")),
                    message=str(recommendation_data.get("message", "")),
                    estimated_score_improvement=float(recommendation_data.get("estimated_score_improvement", 0.0)),
                    confidence=float(recommendation_data.get("confidence", 0.0)),
                )
            )
        return created

    async def mark_applied(
        self,
        session: AsyncSession,
        recommendation_id: UUID,
        *,
        applied_at: datetime | None = None,
    ) -> Recommendation | None:
        recommendation = await self._get_by_id(session, recommendation_id)
        if recommendation is None:
            return None
        recommendation.status = RecommendationLifecycleStatus.APPLIED
        recommendation.applied_at = applied_at or datetime.now(timezone.utc)
        await session.flush()
        await session.refresh(recommendation)
        return recommendation

    async def mark_rejected(
        self,
        session: AsyncSession,
        recommendation_id: UUID,
        *,
        rejected_at: datetime | None = None,
    ) -> Recommendation | None:
        recommendation = await self._get_by_id(session, recommendation_id)
        if recommendation is None:
            return None
        recommendation.status = RecommendationLifecycleStatus.REJECTED
        recommendation.rejected_at = rejected_at or datetime.now(timezone.utc)
        await session.flush()
        await session.refresh(recommendation)
        return recommendation

    async def get_by_execution(
        self,
        session: AsyncSession,
        execution_id: UUID,
    ) -> list[Recommendation]:
        stmt = (
            select(Recommendation)
            .where(Recommendation.execution_id == execution_id)
            .order_by(Recommendation.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_document(
        self,
        session: AsyncSession,
        document_id: UUID,
    ) -> list[Recommendation]:
        stmt = (
            select(Recommendation)
            .where(Recommendation.document_id == document_id)
            .order_by(Recommendation.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _get_by_id(
        self,
        session: AsyncSession,
        recommendation_id: UUID,
    ) -> Recommendation | None:
        stmt = select(Recommendation).where(Recommendation.id == recommendation_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

