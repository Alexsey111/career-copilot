from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes import pipeline_async
from app.main import app
from app.services.pipeline_job_queue import PipelineRunDispatchResult, RedisPipelineJobQueue
from app.workers import pipeline_worker


@dataclass
class _FakeRedis:
    values: dict[str, str]
    items: list[str]

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def rpush(self, key: str, value: str):
        self.items.append(value)

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

    result = await pipeline_worker.run_pipeline_job(payload)

    assert result == str(execution_id)
    assert calls["execution_id"] == execution_id
    assert calls["idempotency_key"] == "idem-worker"
