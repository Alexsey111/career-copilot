from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes import pipeline_async
from app.domain.failure_models import FailureCategory
from app.domain.pipeline_models import PipelineStatus
from app.main import app
from app.services.pipeline_job_queue import (
    DEAD_LETTER_QUEUE_NAME,
    PipelineRunDispatchResult,
    RedisPipelineJobQueue,
)
from app.services.execution_lock_service import ExecutionLockService
from app.workers import pipeline_worker


@dataclass
class _FakeRedis:
    values: dict[str, str]
    items: list[str]

    async def get(self, key: str):
        return self.values.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        px: int | None = None,
    ):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, key: str):
        self.values.pop(key, None)

    async def rpush(self, key: str, value: str):
        self.items.append(value)

    async def lpush(self, key: str, value: str):
        self.items.insert(0, value)

    async def lrange(self, key: str, start: int, end: int):
        if end == -1:
            return self.items[start:]
        return self.items[start:end + 1]

    async def zadd(self, key: str, mapping: dict[str, float]):
        for value, score in mapping.items():
            self.values[f"{key}:{value}"] = str(score)

    async def zrangebyscore(self, key: str, min_score, max_score, start=0, num=None):
        items = []
        prefix = f"{key}:"
        for stored_key, score in self.values.items():
            if stored_key.startswith(prefix) and float(score) <= float(max_score):
                items.append(stored_key.removeprefix(prefix))
        return items[start:start + num if num else None]

    async def zrem(self, key: str, value: str):
        stored_key = f"{key}:{value}"
        existed = stored_key in self.values
        self.values.pop(stored_key, None)
        return 1 if existed else 0

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_pipeline_run_enqueue_endpoint_returns_accepted(client):
    execution_id = uuid4()
    dispatch = PipelineRunDispatchResult(
        execution_id=execution_id,
        job_id=str(execution_id),
        queued=True,
        idempotency_key="idem-1",
        queued_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
    )
    captured: dict[str, object] = {}

    class FakeQueue:
        async def enqueue_pipeline_run(self, **kwargs):
            captured.update(kwargs)
            return PipelineRunDispatchResult(
                execution_id=dispatch.execution_id,
                job_id=dispatch.job_id,
                queued=dispatch.queued,
                idempotency_key=dispatch.idempotency_key,
                queued_at=dispatch.queued_at,
                correlation_id=str(kwargs["correlation_id"]),
            )

    app.dependency_overrides[pipeline_async.get_pipeline_job_queue] = lambda: FakeQueue()
    try:
        response = await client.post(
            "/api/v1/pipeline/run",
            json={
                "user_id": str(uuid4()),
                "document_id": str(uuid4()),
                "vacancy_id": str(uuid4()),
                "pipeline_version": "v1.0",
                "idempotency_key": "idem-1",
            },
        )
    finally:
        app.dependency_overrides.pop(pipeline_async.get_pipeline_job_queue, None)

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["execution_id"] == str(execution_id)
    assert payload["job_id"] == str(execution_id)
    assert payload["status"] == "queued"
    assert payload["queued"] is True
    assert payload["correlation_id"] == str(captured["correlation_id"])
    assert captured["correlation_id"]
    assert response.headers["X-Correlation-ID"]
    assert response.headers["X-Trace-ID"] == response.headers["X-Correlation-ID"]


@pytest.mark.asyncio
async def test_redis_queue_deduplicates_idempotent_runs():
    fake_redis = _FakeRedis(values={}, items=[])
    queue = RedisPipelineJobQueue(redis_client=fake_redis)

    user_id = uuid4()
    document_id = uuid4()
    vacancy_id = uuid4()

    first = await queue.enqueue_pipeline_run(
        user_id=user_id,
        document_id=document_id,
        vacancy_id=vacancy_id,
        pipeline_version="v1.0",
        idempotency_key="idem-queue",
    )
    second = await queue.enqueue_pipeline_run(
        user_id=user_id,
        document_id=document_id,
        vacancy_id=vacancy_id,
        pipeline_version="v1.0",
        idempotency_key="idem-queue",
    )

    assert first.execution_id == second.execution_id
    assert first.queued is True
    assert second.queued is False
    assert len(fake_redis.items) == 1
    queued_payload = json.loads(fake_redis.items[0])
    assert queued_payload["correlation_id"]


@pytest.mark.asyncio
async def test_redis_queue_uses_existing_execution_id_when_provided():
    fake_redis = _FakeRedis(values={}, items=[])
    queue = RedisPipelineJobQueue(redis_client=fake_redis)
    execution_id = uuid4()

    dispatch = await queue.enqueue_pipeline_run(
        execution_id=execution_id,
        user_id=uuid4(),
        document_id=uuid4(),
        vacancy_id=uuid4(),
        pipeline_version="v1.0",
    )

    assert dispatch.execution_id == execution_id
    queued_payload = json.loads(fake_redis.items[0])
    assert queued_payload["execution_id"] == str(execution_id)


@pytest.mark.asyncio
async def test_worker_calls_orchestrator_with_execution_id(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeOrchestrator:
        async def run_pipeline(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(id=str(kwargs["execution_id"]))

    monkeypatch.setattr(pipeline_worker, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(pipeline_worker, "CareerPipelineOrchestrator", FakeOrchestrator)

    execution_id = uuid4()
    payload = {
        "execution_id": str(execution_id),
        "user_id": str(uuid4()),
        "document_id": str(uuid4()),
        "vacancy_id": str(uuid4()),
        "idempotency_key": "idem-worker",
        "correlation_id": "corr-worker",
    }

    fake_redis = _FakeRedis(values={}, items=[])
    result = await pipeline_worker.run_pipeline_job(payload, redis=fake_redis)

    assert result == str(execution_id)
    assert calls["execution_id"] == execution_id
    assert calls["idempotency_key"] == "idem-worker"


@pytest.mark.asyncio
async def test_execution_lock_service_deduplicates_running_execution():
    fake_redis = _FakeRedis(values={}, items=[])
    lock_service = ExecutionLockService(fake_redis)
    execution_id = uuid4()

    assert await lock_service.acquire(execution_id) is True
    assert await lock_service.acquire(execution_id) is False

    await lock_service.release(execution_id)

    assert await lock_service.acquire(execution_id) is True


@pytest.mark.asyncio
async def test_retry_queue_schedules_payload_in_delayed_set():
    fake_redis = _FakeRedis(values={}, items=[])
    queue = RedisPipelineJobQueue(redis_client=fake_redis)
    payload = {
        "execution_id": str(uuid4()),
        "retry_count": "1",
    }

    await queue.requeue_pipeline_run(payload=payload, delay_seconds=5)

    due_now = await fake_redis.zrangebyscore(
        "pipeline:run:retry:jobs",
        0,
        datetime.now(timezone.utc).timestamp(),
        start=0,
        num=10,
    )
    due_later = await fake_redis.zrangebyscore(
        "pipeline:run:retry:jobs",
        0,
        datetime.now(timezone.utc).timestamp() + 10,
        start=0,
        num=10,
    )

    assert due_now == []
    assert [json.loads(item) for item in due_later] == [payload]


def test_worker_retry_decision_helpers():
    runtime_error = RuntimeError("temporary")
    timeout_error = TimeoutError("timeout")
    validation_error = ValueError("bad payload")
    permanent_error = TypeError("bad type")

    assert pipeline_worker._classify_worker_error(runtime_error) == FailureCategory.TRANSIENT
    assert pipeline_worker._classify_worker_error(timeout_error) == FailureCategory.DEPENDENCY
    assert pipeline_worker._classify_worker_error(validation_error) == FailureCategory.VALIDATION
    assert pipeline_worker._classify_worker_error(permanent_error) == FailureCategory.PERMANENT
    assert pipeline_worker._is_retryable_worker_error(runtime_error) is True
    assert pipeline_worker._is_retryable_worker_error(timeout_error) is True
    assert pipeline_worker._is_retryable_worker_error(validation_error) is False
    assert pipeline_worker._is_retryable_worker_error(permanent_error) is False
    assert pipeline_worker._next_retry_delay(0) == 1
    assert pipeline_worker._next_retry_delay(1) == 5
    assert pipeline_worker._next_retry_delay(99) == 120


@pytest.mark.asyncio
async def test_retry_payload_includes_failure_category():
    fake_redis = _FakeRedis(values={}, items=[])
    queue = RedisPipelineJobQueue(redis_client=fake_redis)
    payload = {
        "execution_id": str(uuid4()),
        "retry_count": "1",
        "failure_category": FailureCategory.TRANSIENT.value,
    }

    await queue.requeue_pipeline_run(payload=payload, delay_seconds=0)

    due = await fake_redis.zrangebyscore(
        "pipeline:run:retry:jobs",
        0,
        datetime.now(timezone.utc).timestamp() + 1,
        start=0,
        num=10,
    )

    assert [json.loads(item)["failure_category"] for item in due] == [FailureCategory.TRANSIENT.value]


@pytest.mark.asyncio
async def test_queue_moves_payload_to_dead_letter():
    fake_redis = _FakeRedis(values={}, items=[])
    queue = RedisPipelineJobQueue(redis_client=fake_redis)
    payload = {
        "execution_id": str(uuid4()),
        "retry_count": "4",
    }

    await queue.move_to_dead_letter(payload=payload, reason="retries exhausted")

    assert len(fake_redis.items) == 1
    dead_letter_payload = json.loads(fake_redis.items[0])
    assert dead_letter_payload["execution_id"] == payload["execution_id"]
    assert dead_letter_payload["retry_count"] == "4"
    assert dead_letter_payload["dead_letter_reason"] == "retries exhausted"
    assert dead_letter_payload["dead_lettered_at"]


@pytest.mark.asyncio
async def test_queue_reads_dead_letter_jobs():
    fake_redis = _FakeRedis(values={}, items=[])
    queue = RedisPipelineJobQueue(redis_client=fake_redis)
    first_payload = {
        "execution_id": str(uuid4()),
        "retry_count": "4",
    }
    second_payload = {
        "execution_id": str(uuid4()),
        "retry_count": "5",
    }

    await queue.move_to_dead_letter(payload=first_payload, reason="first")
    await queue.move_to_dead_letter(payload=second_payload, reason="second")

    jobs = await queue.get_dead_letter_jobs(limit=1)

    assert len(jobs) == 1
    assert jobs[0]["execution_id"] == second_payload["execution_id"]
    assert jobs[0]["dead_letter_reason"] == "second"


@pytest.mark.asyncio
async def test_worker_moves_exhausted_retryable_failure_to_dead_letter(monkeypatch):
    fake_redis = _FakeRedis(values={}, items=[])
    execution_id = uuid4()
    payload = {
        "execution_id": str(execution_id),
        "retry_count": str(pipeline_worker.MAX_WORKER_RETRIES),
    }
    fail_calls: list[dict] = []

    async def mark_failed_spy(**kwargs):
        fail_calls.append(kwargs)

    monkeypatch.setattr(pipeline_worker, "_mark_execution_failed_from_worker", mark_failed_spy)

    await pipeline_worker._handle_worker_exception(
        payload=payload,
        exc=RuntimeError("temporary exhausted"),
        redis=fake_redis,
    )

    assert len(fake_redis.items) == 1
    dead_letter_payload = json.loads(fake_redis.items[0])
    assert dead_letter_payload["execution_id"] == str(execution_id)
    assert dead_letter_payload["retry_count"] == str(pipeline_worker.MAX_WORKER_RETRIES)
    assert dead_letter_payload["dead_letter_reason"].startswith("Worker retries exhausted")
    assert dead_letter_payload["dead_lettered_at"]
    assert not any(key.startswith(f"{DEAD_LETTER_QUEUE_NAME}:") for key in fake_redis.values)
    assert fail_calls
    assert fail_calls[0]["retry_count"] == pipeline_worker.MAX_WORKER_RETRIES
    assert fail_calls[0]["failure_category"] == FailureCategory.TRANSIENT
    assert fail_calls[0]["retryable"] is True


@pytest.mark.asyncio
async def test_worker_marks_execution_failed_on_permanent_failure(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def commit(self):
            calls["committed"] = True

    class FakeRepository:
        def __init__(self, session):
            self.session = session

        async def get_execution(self, execution_id):
            return SimpleNamespace(id=str(execution_id), status=PipelineStatus.RUNNING)

    class FakePipelineExecutionService:
        def __init__(self, repository):
            self.repository = repository

        async def fail_execution(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(pipeline_worker, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(pipeline_worker, "SQLAlchemyAsyncPipelineRepository", FakeRepository)
    monkeypatch.setattr(pipeline_worker, "PipelineExecutionService", FakePipelineExecutionService)

    execution_id = uuid4()
    payload = {
        "execution_id": str(execution_id),
    }
    exc = TypeError("worker exploded")

    await pipeline_worker._mark_execution_failed_from_worker(
        payload=payload,
        exc=exc,
        retry_count=4,
        failure_category=FailureCategory.PERMANENT,
        retryable=False,
    )

    assert calls["execution_id"] == execution_id
    assert calls["error_code"] == "TypeError"
    assert calls["error_message"] == "worker exploded"
    assert calls["failed_step"] == "worker"
    assert calls["retry_count"] == 4
    assert calls["failure_category"] == FailureCategory.PERMANENT.value
    assert calls["retryable"] is False
    assert calls["committed"] is True
