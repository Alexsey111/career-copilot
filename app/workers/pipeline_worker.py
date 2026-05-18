"""Background worker entrypoint for pipeline runs."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.core.tracing import clear_trace_context, set_trace_context
from app.services.career_pipeline_orchestrator import CareerPipelineOrchestrator
from app.services.pipeline_job_queue import QUEUE_NAME, RedisPipelineJobQueue

logger = logging.getLogger(__name__)


async def run_pipeline_job(payload: dict[str, str | None]) -> str:
    execution_id = UUID(str(payload["execution_id"]))
    user_id = UUID(str(payload["user_id"]))
    document_id = UUID(str(payload["document_id"]))
    vacancy_id = UUID(str(payload["vacancy_id"]))
    idempotency_key = payload.get("idempotency_key")
    correlation_id = payload.get("correlation_id")

    set_trace_context(trace_id=execution_id, correlation_id=str(correlation_id) if correlation_id else None)

    try:
        async with AsyncSessionLocal() as session:
            orchestrator = CareerPipelineOrchestrator()
            await orchestrator.run_pipeline(
                session=session,
                document_id=document_id,
                vacancy_id=vacancy_id,
                user_id=user_id,
                idempotency_key=str(idempotency_key) if idempotency_key else None,
                execution_id=execution_id,
            )
    finally:
        clear_trace_context()

    return str(execution_id)


async def worker_main() -> None:
    queue = RedisPipelineJobQueue()
    redis = queue._build_client()
    try:
        while True:
            item = await redis.blpop(QUEUE_NAME, timeout=1)
            if item is None:
                await asyncio.sleep(0.1)
                continue

            _, payload_json = item
            payload = json.loads(payload_json)
            try:
                await run_pipeline_job(payload)
            except Exception:
                logger.exception("Pipeline job failed", extra={"execution_id": payload.get("execution_id")})
    finally:
        await redis.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_main())


if __name__ == "__main__":
    main()
