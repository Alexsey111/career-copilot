# app/repositories/evaluation_snapshot_repository.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_snapshot import EvaluationSnapshot


@dataclass
class ResumeMetricsAggregate:
    """Агрегированные метрики resume из БД."""
    count: int
    avg_overall_score: float
    avg_ats_score: float
    avg_evidence_score: float
    avg_coverage_score: float
    avg_quality_score: float


@dataclass
class ReadinessDistribution:
    """Распределение по readiness levels."""
    ready_count: int
    ready_rate: float
    needs_work_count: int
    needs_work_rate: float
    not_ready_count: int
    not_ready_rate: float


@dataclass
class FailureMetricsAggregate:
    """Агрегированные метрики сбоев."""
    total_count: int
    critical_count: int
    critical_failure_rate: float


# Legacy aliases for backward compatibility
ExecutionRecord = FailureMetricsAggregate
RecommendationRecord = ResumeMetricsAggregate


class EvaluationSnapshotRepository:
    """Repository for evaluation snapshots."""

    async def create(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        overall_score: float,
        ats_score: float,
        evidence_score: float,
        coverage_score: float,
        quality_score: float,
        readiness_level: str,
        scoring_version: str,
        prompt_version: str,
        extractor_version: str,
        model_name: str,
        blockers: list[str],
        warnings: list[str],
        metadata: dict | None = None,
        previous_snapshot_id: Optional[UUID] = None,
    ) -> EvaluationSnapshot:
        """Create and persist an evaluation snapshot."""
        snapshot = EvaluationSnapshot(
            document_id=document_id,
            overall_score=overall_score,
            ats_score=ats_score,
            evidence_score=evidence_score,
            coverage_score=coverage_score,
            quality_score=quality_score,
            readiness_level=readiness_level,
            scoring_version=scoring_version,
            prompt_version=prompt_version,
            extractor_version=extractor_version,
            model_name=model_name,
            blockers_json=blockers,
            warnings_json=warnings,
            metadata_json=metadata or {},
            previous_snapshot_id=previous_snapshot_id,
        )
        session.add(snapshot)
        await session.flush()
        await session.refresh(snapshot)
        return snapshot

    async def get_by_id(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
    ) -> Optional[EvaluationSnapshot]:
        """Get snapshot by ID."""
        stmt = select(EvaluationSnapshot).where(
            EvaluationSnapshot.id == snapshot_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_id(
        self,
        session: AsyncSession,
        document_id: UUID,
        limit: int = 50,
    ) -> list[EvaluationSnapshot]:
        """Get snapshots for a document, ordered by creation time."""
        stmt = (
            select(EvaluationSnapshot)
            .where(EvaluationSnapshot.document_id == document_id)
            .order_by(EvaluationSnapshot.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_snapshot_chain(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
    ) -> list[EvaluationSnapshot]:
        """Get chain of snapshots following previous_snapshot_id links."""
        chain = []
        current = await self.get_by_id(session, snapshot_id)

        while current:
            chain.append(current)
            if current.previous_snapshot_id:
                current = await self.get_by_id(session, current.previous_snapshot_id)
            else:
                break

        return chain

    async def get_recent_snapshots(
        self,
        session: AsyncSession,
        limit: int = 100,
    ) -> list[EvaluationSnapshot]:
        """Get recent evaluation snapshots."""
        stmt = (
            select(EvaluationSnapshot)
            .order_by(EvaluationSnapshot.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_snapshots_in_range(
        self,
        session: AsyncSession,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[EvaluationSnapshot]:
        """Get snapshots within a time range."""
        stmt = (
            select(EvaluationSnapshot)
            .where(EvaluationSnapshot.created_at >= start_time)
            .order_by(EvaluationSnapshot.created_at.desc())
            .limit(limit)
        )

        if end_time:
            stmt = stmt.where(EvaluationSnapshot.created_at <= end_time)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_average_scores(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, float]:
        """Get average scores across all snapshots in range."""
        stmt = select(
            func.avg(EvaluationSnapshot.overall_score).label('avg_overall'),
            func.avg(EvaluationSnapshot.ats_score).label('avg_ats'),
            func.avg(EvaluationSnapshot.evidence_score).label('avg_evidence'),
            func.avg(EvaluationSnapshot.coverage_score).label('avg_coverage'),
            func.avg(EvaluationSnapshot.quality_score).label('avg_quality'),
        )

        if start_time:
            stmt = stmt.where(EvaluationSnapshot.created_at >= start_time)
        if end_time:
            stmt = stmt.where(EvaluationSnapshot.created_at <= end_time)

        result = await session.execute(stmt)
        row = result.one()

        return {
            'avg_overall': row.avg_overall or 0.0,
            'avg_ats': row.avg_ats or 0.0,
            'avg_evidence': row.avg_evidence or 0.0,
            'avg_coverage': row.avg_coverage or 0.0,
            'avg_quality': row.avg_quality or 0.0,
        }

    async def get_count(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Get count of snapshots in range."""
        stmt = select(func.count(EvaluationSnapshot.id))

        if start_time:
            stmt = stmt.where(EvaluationSnapshot.created_at >= start_time)
        if end_time:
            stmt = stmt.where(EvaluationSnapshot.created_at <= end_time)

        result = await session.execute(stmt)
        return result.scalar_one() or 0

    async def get_resume_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> ResumeMetricsAggregate:
        """
        Get aggregated resume metrics using SQL aggregation.

        SQL:
            SELECT
                COUNT(*),
                AVG(overall_score),
                AVG(ats_score),
                AVG(evidence_score),
                AVG(coverage_score),
                AVG(quality_score)
            FROM evaluation_snapshots
            WHERE created_at >= :start_time
        """
        stmt = select(
            func.count(EvaluationSnapshot.id).label('count'),
            func.coalesce(func.avg(EvaluationSnapshot.overall_score), 0.0).label('avg_overall'),
            func.coalesce(func.avg(EvaluationSnapshot.ats_score), 0.0).label('avg_ats'),
            func.coalesce(func.avg(EvaluationSnapshot.evidence_score), 0.0).label('avg_evidence'),
            func.coalesce(func.avg(EvaluationSnapshot.coverage_score), 0.0).label('avg_coverage'),
            func.coalesce(func.avg(EvaluationSnapshot.quality_score), 0.0).label('avg_quality'),
        )

        if start_time:
            stmt = stmt.where(EvaluationSnapshot.created_at >= start_time)
        if end_time:
            stmt = stmt.where(EvaluationSnapshot.created_at <= end_time)

        result = await session.execute(stmt)
        row = result.one()

        return ResumeMetricsAggregate(
            count=row.count,
            avg_overall_score=row.avg_overall,
            avg_ats_score=row.avg_ats,
            avg_evidence_score=row.avg_evidence,
            avg_coverage_score=row.avg_coverage,
            avg_quality_score=row.avg_quality,
        )

    async def get_readiness_distribution(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> ReadinessDistribution:
        """
        Get readiness level distribution using SQL aggregation.

        SQL:
            SELECT
                SUM(CASE WHEN readiness_level = 'ready' THEN 1 ELSE 0 END) as ready_count,
                SUM(CASE WHEN readiness_level = 'needs_work' THEN 1 ELSE 0 END) as needs_work_count,
                SUM(CASE WHEN readiness_level = 'not_ready' THEN 1 ELSE 0 END) as not_ready_count,
                COUNT(*) as total
            FROM evaluation_snapshots
            WHERE created_at >= :start_time
        """
        stmt = select(
            func.sum(
                func.case(
                    (EvaluationSnapshot.readiness_level == 'ready', 1),
                    else_=0
                )
            ).label('ready_count'),
            func.sum(
                func.case(
                    (EvaluationSnapshot.readiness_level == 'needs_work', 1),
                    else_=0
                )
            ).label('needs_work_count'),
            func.sum(
                func.case(
                    (EvaluationSnapshot.readiness_level == 'not_ready', 1),
                    else_=0
                )
            ).label('not_ready_count'),
            func.count(EvaluationSnapshot.id).label('total'),
        )

        if start_time:
            stmt = stmt.where(EvaluationSnapshot.created_at >= start_time)
        if end_time:
            stmt = stmt.where(EvaluationSnapshot.created_at <= end_time)

        result = await session.execute(stmt)
        row = result.one()

        total = row.total or 0

        return ReadinessDistribution(
            ready_count=row.ready_count or 0,
            ready_rate=(row.ready_count or 0) / total if total > 0 else 0.0,
            needs_work_count=row.needs_work_count or 0,
            needs_work_rate=(row.needs_work_count or 0) / total if total > 0 else 0.0,
            not_ready_count=row.not_ready_count or 0,
            not_ready_rate=(row.not_ready_count or 0) / total if total > 0 else 0.0,
        )

    async def get_failure_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> FailureMetricsAggregate:
        """
        Get failure metrics using SQL aggregation.

        SQL:
            SELECT
                COUNT(*),
                SUM(CASE WHEN readiness_level = 'not_ready' AND blockers_json IS NOT NULL AND blockers_json != '[]' THEN 1 ELSE 0 END)
            FROM evaluation_snapshots
            WHERE created_at >= :start_time
        """
        stmt = select(
            func.count(EvaluationSnapshot.id).label('total'),
            func.sum(
                func.case(
                    (
                        (EvaluationSnapshot.readiness_level == 'not_ready') &
                        (EvaluationSnapshot.blockers_json.isnot(None)) &
                        (EvaluationSnapshot.blockers_json != Text('[]'))
                    ), 1
                ),
                else_=0
            ).label('critical_count'),
        )

        if start_time:
            stmt = stmt.where(EvaluationSnapshot.created_at >= start_time)
        if end_time:
            stmt = stmt.where(EvaluationSnapshot.created_at <= end_time)

        result = await session.execute(stmt)
        row = result.one()

        total = row.total or 0
        critical = row.critical_count or 0

        return FailureMetricsAggregate(
            total_count=total,
            critical_count=critical,
            critical_failure_rate=critical / total if total > 0 else 0.0,
        )

    async def get_review_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> ReadinessDistribution:
        """
        Get review-required metrics (same as readiness distribution for needs_work).

        Uses same SQL as get_readiness_distribution.
        """
        return await self.get_readiness_distribution(session, start_time, end_time)
