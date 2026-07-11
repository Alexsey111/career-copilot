# app/tasks/pipeline_tasks.py

from __future__ import annotations

import logging
from uuid import UUID

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.pipeline_tasks.run_pipeline",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_pipeline(
    self,
    execution_id: str,
    user_id: str,
    document_id: str,
    vacancy_id: str,
) -> dict:
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.services.career_pipeline_orchestrator import CareerPipelineOrchestrator

    async def _run():
        async with AsyncSessionLocal() as session:
            orchestrator = CareerPipelineOrchestrator()
            await orchestrator.run_pipeline(
                session=session,
                document_id=UUID(document_id),
                vacancy_id=UUID(vacancy_id),
                user_id=UUID(user_id),
                execution_id=UUID(execution_id),
            )
            return {
                "execution_id": execution_id,
                "status": "completed",
            }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("run_pipeline failed", extra={"execution_id": execution_id})
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.pipeline_tasks.cleanup_stale_executions")
def cleanup_stale_executions() -> dict:
    import asyncio
    from datetime import datetime, timezone, timedelta
    from app.db.session import AsyncSessionLocal
    from app.models import PipelineExecution
    from sqlalchemy import update

    async def _run():
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            stmt = (
                update(PipelineExecution)
                .where(PipelineExecution.status == "running")
                .where(PipelineExecution.updated_at < cutoff)
                .values(status="failed", error_message="stale execution cleaned up by beat")
            )
            result = await session.execute(stmt)
            await session.commit()
            return {"cleaned": result.rowcount}

    return asyncio.get_event_loop().run_until_complete(_run())
