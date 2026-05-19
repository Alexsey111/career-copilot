"""Operational runtime snapshots for pipeline executions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.pipeline_execution_repository import PipelineExecutionRepository
from app.services.stuck_execution_service import StuckExecutionService


@dataclass(slots=True)
class ExecutionRuntimeSnapshot:
    running_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    retry_total: int
    stuck_count: int
    avg_execution_duration_ms: float
    avg_evaluation_duration_ms: float
    avg_mutation_duration_ms: float


class ExecutionObservabilityService:
    """Read-only operational snapshot service for execution runtime state."""

    def __init__(
        self,
        pipeline_repository: PipelineExecutionRepository,
        stuck_execution_service: StuckExecutionService,
    ) -> None:
        self._pipeline_repository = pipeline_repository
        self._stuck_service = stuck_execution_service

    async def get_execution_runtime_snapshot(
        self,
        session: AsyncSession,
    ) -> ExecutionRuntimeSnapshot:
        aggregate = await self._pipeline_repository.get_runtime_aggregate(session)

        older_than = datetime.now(timezone.utc) - timedelta(minutes=30)
        stuck_executions = await self._stuck_service._pipeline_service.get_stuck_executions(
            older_than=older_than,
            limit=1000,
        )

        return ExecutionRuntimeSnapshot(
            running_count=aggregate.running_count,
            completed_count=aggregate.completed_count,
            failed_count=aggregate.failed_count,
            cancelled_count=aggregate.cancelled_count,
            retry_total=aggregate.retry_total,
            stuck_count=len(stuck_executions),
            avg_execution_duration_ms=aggregate.avg_execution_duration_ms,
            avg_evaluation_duration_ms=aggregate.avg_evaluation_duration_ms,
            avg_mutation_duration_ms=aggregate.avg_mutation_duration_ms,
        )
