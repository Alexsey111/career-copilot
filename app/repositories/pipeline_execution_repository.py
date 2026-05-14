# app/repositories/pipeline_execution_repository.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import PipelineExecution


@dataclass
class PipelineDurationMetrics:
    """Агрегированные метрики длительности pipeline."""
    count: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float
    p90_duration_ms: float
    avg_evaluation_duration_ms: float = 0.0
    avg_mutation_duration_ms: float = 0.0


@dataclass
class PipelineSuccessMetrics:
    """Агрегированные метрики успеха pipeline."""
    total_count: int
    completed_count: int
    failed_count: int
    completion_rate: float
    success_rate: float
    failure_rate: float


@dataclass
class PipelineFailureMetrics:
    """Агрегированные метрики сбоев pipeline."""
    total_count: int
    failed_count: int
    failure_rate: float
    top_failure_codes: list[tuple[str, int]]


class PipelineExecutionRepository:
    """Repository for pipeline executions with SQL aggregation."""

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        document_id: Optional[UUID],
        execution_type: str,
        trigger_type: str,
        status: str,
        started_at: datetime,
        output_artifact_ids: list[str] | None = None,
        input_params: dict | None = None,
        metadata: dict | None = None,
    ) -> PipelineExecution:
        """Create and persist a pipeline execution record."""
        execution = PipelineExecution(
            user_id=user_id,
            document_id=document_id,
            execution_type=execution_type,
            trigger_type=trigger_type,
            status=status,
            started_at=started_at,
            output_artifact_ids=output_artifact_ids or [],
            input_params=input_params or {},
            metadata_json=metadata or {},
        )
        session.add(execution)
        await session.flush()
        await session.refresh(execution)
        return execution

    async def update_status(
        self,
        session: AsyncSession,
        execution_id: UUID,
        status: str,
        completed_at: Optional[datetime] = None,
        failure_reason: Optional[str] = None,
        failure_code: Optional[str] = None,
    ) -> PipelineExecution | None:
        """Update execution status and optional completion info."""
        stmt = select(PipelineExecution).where(
            PipelineExecution.id == execution_id
        )
        result = await session.execute(stmt)
        execution = result.scalar_one_or_none()

        if execution:
            execution.status = status
            if completed_at:
                execution.completed_at = completed_at
                if execution.started_at:
                    execution.execution_duration_ms = int(
                        (completed_at - execution.started_at).total_seconds() * 1000
                    )
                    execution.duration_ms = execution.execution_duration_ms
            if failure_reason:
                execution.failure_reason = failure_reason
            if failure_code:
                execution.failure_code = failure_code

            await session.flush()
            await session.refresh(execution)

        return execution

    async def get_by_id(
        self,
        session: AsyncSession,
        execution_id: UUID,
    ) -> PipelineExecution | None:
        """Get execution by ID."""
        stmt = select(PipelineExecution).where(
            PipelineExecution.id == execution_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        session: AsyncSession,
        user_id: UUID,
        limit: int = 50,
    ) -> list[PipelineExecution]:
        """Get recent executions for a user."""
        stmt = (
            select(PipelineExecution)
            .where(PipelineExecution.user_id == user_id)
            .order_by(PipelineExecution.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_executions(
        self,
        session: AsyncSession,
        limit: int = 100,
    ) -> list[PipelineExecution]:
        """Get recent pipeline executions."""
        stmt = (
            select(PipelineExecution)
            .order_by(PipelineExecution.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_executions_in_range(
        self,
        session: AsyncSession,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        execution_type: Optional[str] = None,
        limit: int = 1000,
    ) -> list[PipelineExecution]:
        """Get executions within a time range."""
        stmt = (
            select(PipelineExecution)
            .where(PipelineExecution.created_at >= start_time)
            .order_by(PipelineExecution.created_at.desc())
            .limit(limit)
        )

        if end_time:
            stmt = stmt.where(PipelineExecution.created_at <= end_time)
        if execution_type:
            stmt = stmt.where(PipelineExecution.execution_type == execution_type)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_duration_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        execution_type: Optional[str] = None,
    ) -> PipelineDurationMetrics:
        """
        Get aggregated duration metrics using SQL.

        SQL:
            SELECT
                COUNT(*),
                AVG(duration_ms),
                MIN(duration_ms),
                MAX(duration_ms)
            FROM pipeline_executions
            WHERE status = 'completed' AND created_at >= :start_time
        """
        duration_expr = func.coalesce(
            PipelineExecution.execution_duration_ms,
            func.extract("epoch", PipelineExecution.completed_at - PipelineExecution.started_at) * 1000,
        )
        evaluation_expr = func.coalesce(PipelineExecution.evaluation_duration_ms, 0.0)
        mutation_expr = func.coalesce(PipelineExecution.mutation_duration_ms, 0.0)

        stmt = select(
            func.count(PipelineExecution.id).label('count'),
            func.coalesce(func.avg(duration_expr), 0.0).label('avg_duration'),
            func.coalesce(func.min(duration_expr), 0.0).label('min_duration'),
            func.coalesce(func.max(duration_expr), 0.0).label('max_duration'),
            func.coalesce(func.avg(evaluation_expr), 0.0).label('avg_evaluation_duration'),
            func.coalesce(func.avg(mutation_expr), 0.0).label('avg_mutation_duration'),
        )

        stmt = stmt.where(PipelineExecution.status == 'completed')
        if start_time:
            stmt = stmt.where(PipelineExecution.created_at >= start_time)
        if end_time:
            stmt = stmt.where(PipelineExecution.created_at <= end_time)
        if execution_type:
            stmt = stmt.where(PipelineExecution.execution_type == execution_type)

        result = await session.execute(stmt)
        row = result.one()

        return PipelineDurationMetrics(
            count=row.count,
            avg_duration_ms=row.avg_duration,
            min_duration_ms=row.min_duration,
            max_duration_ms=row.max_duration,
            p50_duration_ms=0.0,  # TODO: compute percentile with window functions
            p90_duration_ms=0.0,
            avg_evaluation_duration_ms=row.avg_evaluation_duration,
            avg_mutation_duration_ms=row.avg_mutation_duration,
        )

    async def get_success_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        execution_type: Optional[str] = None,
    ) -> PipelineSuccessMetrics:
        """
        Get aggregated success metrics using SQL.

        SQL:
            SELECT
                COUNT(*),
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
            FROM pipeline_executions
            WHERE created_at >= :start_time
        """
        stmt = select(
            func.count(PipelineExecution.id).label('total'),
            func.sum(
                func.case(
                    (PipelineExecution.status == 'completed', 1),
                    else_=0
                )
            ).label('completed'),
            func.sum(
                func.case(
                    (PipelineExecution.status == 'failed', 1),
                    else_=0
                )
            ).label('failed'),
        )

        if start_time:
            stmt = stmt.where(PipelineExecution.created_at >= start_time)
        if end_time:
            stmt = stmt.where(PipelineExecution.created_at <= end_time)
        if execution_type:
            stmt = stmt.where(PipelineExecution.execution_type == execution_type)

        result = await session.execute(stmt)
        row = result.one()

        total = row.total or 0
        completed = row.completed or 0
        failed = row.failed or 0

        return PipelineSuccessMetrics(
            total_count=total,
            completed_count=completed,
            failed_count=failed,
            completion_rate=completed / total if total > 0 else 0.0,
            success_rate=completed / total if total > 0 else 0.0,
            failure_rate=failed / total if total > 0 else 0.0,
        )

    async def get_failure_metrics(
        self,
        session: AsyncSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> PipelineFailureMetrics:
        """
        Get aggregated failure metrics using SQL.

        SQL:
            SELECT
                COUNT(*),
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
            FROM pipeline_executions
            WHERE created_at >= :start_time
        """
        # Get total and failed counts
        count_stmt = select(
            func.count(PipelineExecution.id).label('total'),
            func.sum(
                func.case(
                    (PipelineExecution.status == 'failed', 1),
                    else_=0
                )
            ).label('failed'),
        )

        if start_time:
            count_stmt = count_stmt.where(PipelineExecution.created_at >= start_time)
        if end_time:
            count_stmt = count_stmt.where(PipelineExecution.created_at <= end_time)

        count_result = await session.execute(count_stmt)
        count_row = count_result.one()

        total = count_row.total or 0
        failed = count_row.failed or 0

        # Get top failure codes
        failure_codes_stmt = (
            select(
                PipelineExecution.failure_code,
                func.count(PipelineExecution.id).label('count'),
            )
            .where(PipelineExecution.status == 'failed')
            .where(PipelineExecution.failure_code.isnot(None))
            .group_by(PipelineExecution.failure_code)
            .order_by(func.count(PipelineExecution.id).desc())
            .limit(10)
        )

        if start_time:
            failure_codes_stmt = failure_codes_stmt.where(
                PipelineExecution.created_at >= start_time
            )
        if end_time:
            failure_codes_stmt = failure_codes_stmt.where(
                PipelineExecution.created_at <= end_time
            )

        codes_result = await session.execute(failure_codes_stmt)
        top_codes = list(codes_result.all())

        return PipelineFailureMetrics(
            total_count=total,
            failed_count=failed,
            failure_rate=failed / total if total > 0 else 0.0,
            top_failure_codes=[(code, count) for code, count in top_codes],
        )
