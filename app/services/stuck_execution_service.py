"""Service for marking long-running pipeline executions as failed."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.domain.failure_models import FailureCategory
from app.services.pipeline_execution_service import PipelineExecutionService


class StuckExecutionService:
    def __init__(
        self,
        pipeline_service: PipelineExecutionService,
        threshold_minutes: int = 30,
    ) -> None:
        self._pipeline_service = pipeline_service
        self._threshold = timedelta(minutes=threshold_minutes)

    async def mark_stuck_executions_failed(self, *, limit: int = 100) -> int:
        older_than = datetime.now(timezone.utc) - self._threshold

        executions = await self._pipeline_service.get_stuck_executions(
            older_than=older_than,
            limit=limit,
        )

        marked_count = 0
        for execution in executions:
            await self._pipeline_service.fail_execution(
                execution_id=UUID(execution.id),
                error_code="StuckExecutionTimeout",
                error_message=f"Execution exceeded running threshold of {self._threshold}.",
                failed_step="stuck_execution_detector",
                retry_count=execution.retry_count,
                failure_category=FailureCategory.TRANSIENT.value,
                retryable=True,
            )
            marked_count += 1

        return marked_count
