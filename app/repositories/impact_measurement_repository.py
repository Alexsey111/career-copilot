# app/repositories/impact_measurement_repository.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.impact_measurement import ImpactMeasurement, ImpactRecommendationType


@dataclass
class RecommendationImpactAggregate:
    """SQL-aggregated recommendation impact metrics."""
    completed_count: int
    positive_impact_count: int
    average_readiness_improvement: float
    completion_count_by_type: dict[str, int]


class ImpactMeasurementRepository:
    """Repository for impact measurements."""

    async def create(
        self,
        session: AsyncSession,
        *,
        recommendation_id: str,
        recommendation_type: ImpactRecommendationType,
        document_id: UUID,
        before_snapshot_id: UUID,
        after_snapshot_id: UUID,
        delta_overall: float,
        delta_components: dict[str, float],
    ) -> ImpactMeasurement:
        """Create and persist an impact measurement."""
        measurement = ImpactMeasurement(
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
            document_id=document_id,
            before_snapshot_id=before_snapshot_id,
            after_snapshot_id=after_snapshot_id,
            delta_overall=delta_overall,
            delta_components=delta_components,
        )
        session.add(measurement)
        await session.flush()
        await session.refresh(measurement)
        return measurement

    async def get_by_recommendation_id(
        self,
        session: AsyncSession,
        recommendation_id: str,
    ) -> ImpactMeasurement | None:
        """Get impact measurement by recommendation ID."""
        stmt = select(ImpactMeasurement).where(
            ImpactMeasurement.recommendation_id == recommendation_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_id(
        self,
        session: AsyncSession,
        document_id: UUID,
        limit: int = 50,
    ) -> list[ImpactMeasurement]:
        """Get impact measurements for a document."""
        stmt = (
            select(ImpactMeasurement)
            .where(ImpactMeasurement.document_id == document_id)
            .order_by(ImpactMeasurement.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_measurements(
        self,
        session: AsyncSession,
        limit: int = 100,
    ) -> list[ImpactMeasurement]:
        """Get recent impact measurements."""
        stmt = (
            select(ImpactMeasurement)
            .order_by(ImpactMeasurement.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_recommendation_impact_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> RecommendationImpactAggregate:
        """
        Aggregate recommendation impact metrics directly in SQL.
        """
        summary_stmt = select(
            func.count(ImpactMeasurement.id).label("completed_count"),
            func.sum(
                func.case((ImpactMeasurement.delta_overall > 0, 1), else_=0)
            ).label("positive_impact_count"),
            func.coalesce(func.avg(ImpactMeasurement.delta_overall), 0.0).label("avg_delta"),
        )

        if start_time:
            summary_stmt = summary_stmt.where(ImpactMeasurement.created_at >= start_time)
        if end_time:
            summary_stmt = summary_stmt.where(ImpactMeasurement.created_at <= end_time)

        summary_row = (await session.execute(summary_stmt)).one()

        by_type_stmt = select(
            ImpactMeasurement.recommendation_type.label("recommendation_type"),
            func.count(ImpactMeasurement.id).label("count"),
        ).group_by(ImpactMeasurement.recommendation_type)

        if start_time:
            by_type_stmt = by_type_stmt.where(ImpactMeasurement.created_at >= start_time)
        if end_time:
            by_type_stmt = by_type_stmt.where(ImpactMeasurement.created_at <= end_time)

        by_type_rows = (await session.execute(by_type_stmt)).all()

        return RecommendationImpactAggregate(
            completed_count=summary_row.completed_count or 0,
            positive_impact_count=summary_row.positive_impact_count or 0,
            average_readiness_improvement=summary_row.avg_delta or 0.0,
            completion_count_by_type={
                (row.recommendation_type.value if row.recommendation_type else ImpactRecommendationType.UNKNOWN.value): row.count
                for row in by_type_rows
            },
        )