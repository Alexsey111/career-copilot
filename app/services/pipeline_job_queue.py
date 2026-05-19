"""Redis-backed queue for background pipeline execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from redis.asyncio import Redis, from_url

from app.core.config import get_settings
from app.core.tracing import get_trace_context, new_correlation_id

QUEUE_NAME = "pipeline:run:jobs"
RETRY_QUEUE_NAME = "pipeline:run:retry:jobs"
DEAD_LETTER_QUEUE_NAME = "pipeline:run:dead-letter"
IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24


@dataclass(slots=True, frozen=True)
class PipelineRunDispatchResult:
    execution_id: UUID
    job_id: str
    queued: bool
    idempotency_key: str | None
    queued_at: datetime
    correlation_id: str | None = None


class RedisPipelineJobQueue:
    """Minimal Redis queue for pipeline runs."""

    def __init__(self, redis_client: Redis | None = None) -> None:
        self._redis_client = redis_client

    async def enqueue_pipeline_run(
        self,
        *,
        execution_id: UUID | None = None,
        user_id: UUID,
        document_id: UUID,
        vacancy_id: UUID,
        pipeline_version: str,
        calibration_version: str | None = None,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> PipelineRunDispatchResult:
        redis = self._redis_client or self._build_client()
        created_client = self._redis_client is None

        execution_id = execution_id or uuid4()
        queued_at = datetime.now(timezone.utc)
        resolved_correlation_id = correlation_id or get_trace_context().correlation_id or new_correlation_id()
        queue_key = (
            self._idempotency_key(user_id, document_id, vacancy_id, idempotency_key)
            if idempotency_key
            else None
        )

        try:
            if queue_key is not None:
                existing_job_id = await redis.get(queue_key)
                if existing_job_id:
                    return PipelineRunDispatchResult(
                        execution_id=UUID(str(existing_job_id)),
                        job_id=str(existing_job_id),
                        queued=False,
                        idempotency_key=idempotency_key,
                        correlation_id=resolved_correlation_id,
                        queued_at=queued_at,
                    )

                reserved = await redis.set(
                    queue_key,
                    str(execution_id),
                    ex=IDEMPOTENCY_TTL_SECONDS,
                    nx=True,
                )
                if not reserved:
                    existing_job_id = await redis.get(queue_key)
                    if existing_job_id:
                        return PipelineRunDispatchResult(
                            execution_id=UUID(str(existing_job_id)),
                            job_id=str(existing_job_id),
                            queued=False,
                            idempotency_key=idempotency_key,
                            correlation_id=resolved_correlation_id,
                            queued_at=queued_at,
                        )

            payload = {
                "execution_id": str(execution_id),
                "user_id": str(user_id),
                "document_id": str(document_id),
                "vacancy_id": str(vacancy_id),
                "pipeline_version": pipeline_version,
                "calibration_version": calibration_version,
                "idempotency_key": idempotency_key,
                "correlation_id": resolved_correlation_id,
                "queued_at": queued_at.isoformat(),
            }
            await redis.rpush(QUEUE_NAME, json.dumps(payload))
            return PipelineRunDispatchResult(
                execution_id=execution_id,
                job_id=str(execution_id),
                queued=True,
                idempotency_key=idempotency_key,
                correlation_id=resolved_correlation_id,
                queued_at=queued_at,
            )
        finally:
            if created_client:
                await redis.aclose()

    async def requeue_pipeline_run(
        self,
        *,
        payload: dict,
        delay_seconds: int,
    ) -> None:
        redis = self._redis_client or self._build_client()
        created_client = self._redis_client is None

        try:
            run_at = datetime.now(timezone.utc).timestamp() + delay_seconds
            await redis.zadd(
                RETRY_QUEUE_NAME,
                {json.dumps(payload): run_at},
            )
        finally:
            if created_client:
                await redis.aclose()

    async def move_to_dead_letter(
        self,
        *,
        payload: dict,
        reason: str,
    ) -> None:
        redis = self._redis_client or self._build_client()
        created_client = self._redis_client is None

        try:
            dead_letter_payload = {
                **payload,
                "dead_letter_reason": reason,
                "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
            }
            await redis.lpush(DEAD_LETTER_QUEUE_NAME, json.dumps(dead_letter_payload))
        finally:
            if created_client:
                await redis.aclose()

    async def get_dead_letter_jobs(self, *, limit: int = 100) -> list[dict]:
        redis = self._redis_client or self._build_client()
        created_client = self._redis_client is None

        try:
            items = await redis.lrange(DEAD_LETTER_QUEUE_NAME, 0, max(limit - 1, 0))
            return [json.loads(item) for item in items]
        finally:
            if created_client:
                await redis.aclose()

    @staticmethod
    def _build_client() -> Redis:
        settings = get_settings()
        return from_url(f"redis://{settings.redis_host}:{settings.redis_port}/0", decode_responses=True)

    @staticmethod
    def _idempotency_key(
        user_id: UUID,
        document_id: UUID,
        vacancy_id: UUID,
        idempotency_key: str | None,
    ) -> str:
        if not idempotency_key:
            raise ValueError("idempotency_key is required for queue deduplication")
        return f"pipeline:run:idempotency:{user_id}:{document_id}:{vacancy_id}:{idempotency_key}"
