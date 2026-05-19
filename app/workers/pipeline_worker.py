"""Background worker entrypoint for pipeline runs."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis

from app.db.session import AsyncSessionLocal
from app.core.tracing import clear_trace_context, set_trace_context
from app.domain.failure_models import FailureCategory, classify_failure, is_retryable_failure
from app.domain.pipeline_models import PipelineStatus
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.services.career_pipeline_orchestrator import CareerPipelineOrchestrator
from app.services.execution_lock_service import ExecutionLockService
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.pipeline_job_queue import QUEUE_NAME, RETRY_QUEUE_NAME, RedisPipelineJobQueue

logger = logging.getLogger(__name__)

MAX_WORKER_RETRIES = 4
WORKER_RETRY_DELAYS = [1, 5, 30, 120]


def _is_retryable_worker_error(exc: Exception) -> bool:
    return is_retryable_failure(_classify_worker_error(exc))


def _classify_worker_error(exc: Exception) -> FailureCategory:
    return classify_failure(exc)


def _next_retry_delay(retry_count: int) -> int:
    index = min(retry_count, len(WORKER_RETRY_DELAYS) - 1)
    return WORKER_RETRY_DELAYS[index]


async def _mark_execution_failed_from_worker(
    *,
    payload: dict[str, str | None],
    exc: Exception,
    retry_count: int,
    failure_category: FailureCategory,
    retryable: bool,
) -> None:
    try:
        execution_id = UUID(str(payload["execution_id"]))
        async with AsyncSessionLocal() as session:
            repository = SQLAlchemyAsyncPipelineRepository(session)
            execution = await repository.get_execution(execution_id)
            if execution is not None and execution.status == PipelineStatus.FAILED:
                return

            pipeline_service = PipelineExecutionService(repository)
            await pipeline_service.fail_execution(
                execution_id=execution_id,
                error_code=type(exc).__name__,
                error_message=str(exc),
                failed_step="worker",
                retry_count=retry_count,
                failure_category=failure_category.value,
                retryable=retryable,
                session=session,
            )

            commit = getattr(session, "commit", None)
            if commit is not None:
                await commit()
    except Exception:
        logger.exception(
            "Worker fallback fail_execution failed",
            extra={
                "execution_id": payload.get("execution_id"),
            },
        )


async def run_pipeline_job(payload: dict[str, str | None], redis: Redis | None = None) -> str:
    execution_id = UUID(str(payload["execution_id"]))
    user_id = UUID(str(payload["user_id"]))
    document_id = UUID(str(payload["document_id"]))
    vacancy_id = UUID(str(payload["vacancy_id"]))
    idempotency_key = payload.get("idempotency_key")
    correlation_id = payload.get("correlation_id")

    set_trace_context(trace_id=execution_id, correlation_id=str(correlation_id) if correlation_id else None)

    created_redis = redis is None
    redis_client = redis or RedisPipelineJobQueue._build_client()
    lock_service = ExecutionLockService(redis_client)
    locked = await lock_service.acquire(execution_id)
    if not locked:
        logger.warning(
            "Pipeline execution already locked",
            extra={"execution_id": str(execution_id)},
        )
        clear_trace_context()
        if created_redis:
            await redis_client.aclose()
        return str(execution_id)

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
        if locked:
            await lock_service.release(execution_id)
        clear_trace_context()
        if created_redis:
            await redis_client.aclose()

    return str(execution_id)


async def _handle_worker_exception(
    *,
    payload: dict,
    exc: Exception,
    redis: Redis,
) -> None:
    retry_count = int(payload.get("retry_count") or 0)
    failure_category = _classify_worker_error(exc)
    retryable = is_retryable_failure(failure_category)
    queue = RedisPipelineJobQueue(redis_client=redis)

    if retryable and retry_count < MAX_WORKER_RETRIES:
        payload["retry_count"] = str(retry_count + 1)
        payload["failure_category"] = failure_category.value
        delay_seconds = _next_retry_delay(retry_count)

        await queue.requeue_pipeline_run(
            payload=payload,
            delay_seconds=delay_seconds,
        )

        logger.warning(
            "Pipeline job scheduled for retry",
            extra={
                "execution_id": payload.get("execution_id"),
                "failure_category": failure_category.value,
                "retryable": retryable,
                "retry_count": retry_count + 1,
                "delay_seconds": delay_seconds,
            },
        )
        return

    logger.exception(
        "Pipeline job failed permanently",
        extra={
            "execution_id": payload.get("execution_id"),
            "failure_category": failure_category.value,
            "retryable": retryable,
            "retry_count": retry_count,
        },
    )

    if retry_count >= MAX_WORKER_RETRIES:
        await queue.move_to_dead_letter(
            payload=payload,
            reason=f"Worker retries exhausted after {retry_count} attempts: {type(exc).__name__}: {exc}",
        )

    await _mark_execution_failed_from_worker(
        payload=payload,
        exc=exc,
        retry_count=retry_count,
        failure_category=failure_category,
        retryable=retryable,
    )


async def worker_main() -> None:
    queue = RedisPipelineJobQueue()
    redis = queue._build_client()
    try:
        while True:
            now_ts = datetime.now(timezone.utc).timestamp()
            due_items = await redis.zrangebyscore(RETRY_QUEUE_NAME, 0, now_ts, start=0, num=10)
            for retry_payload_json in due_items:
                removed = await redis.zrem(RETRY_QUEUE_NAME, retry_payload_json)
                if removed:
                    await redis.rpush(QUEUE_NAME, retry_payload_json)

            item = await redis.blpop(QUEUE_NAME, timeout=1)
            if item is None:
                await asyncio.sleep(0.1)
                continue

            _, payload_json = item
            payload = json.loads(payload_json)
            try:
                await run_pipeline_job(payload, redis=redis)
            except Exception as exc:
                await _handle_worker_exception(payload=payload, exc=exc, redis=redis)
    finally:
        await redis.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_main())


if __name__ == "__main__":
    main()
