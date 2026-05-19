# Execution Runtime Platform

## 1. What this layer does

Execution Runtime Platform is the operational layer around Career Copilot pipeline runs. It makes pipeline execution observable, deduplicated, retryable, cancellable, and recoverable from common runtime failure modes.

The layer does not provide a full observability platform, replay system, or admin UI yet. Its current goal is pragmatic runtime control and visibility using Redis, SQL aggregation, immutable execution events, and small API endpoints.

## 2. Runtime components

- `RedisPipelineJobQueue`: enqueues pipeline jobs, schedules delayed retries, and stores exhausted jobs in DLQ.
- `ExecutionLockService`: prevents two workers from running the same `execution_id` at the same time.
- `pipeline_worker`: consumes Redis jobs, applies lock/retry/DLQ/fallback failure behavior.
- `CareerPipelineOrchestrator`: runs tracked pipeline phases and performs cooperative cancellation checks.
- `PipelineExecutionService`: owns execution lifecycle transitions, step tracking, cancellation, failure persistence, and event emission.
- `StuckExecutionService`: marks old running executions as failed.
- `ExecutionObservabilityService`: returns runtime snapshot counts and duration averages.
- `PipelineExecutionRepository`: provides SQL aggregates for runtime and phase analytics.

## 3. Queue flow

1. API receives an async pipeline run request.
2. `RedisPipelineJobQueue.enqueue_pipeline_run()` creates an `execution_id`.
3. If an idempotency key is provided, Redis reserves it for 24 hours.
4. The job payload is pushed to `pipeline:run:jobs`.
5. `pipeline_worker.worker_main()` pops jobs and calls `run_pipeline_job()`.
6. `ExecutionLockService` acquires `pipeline:execution:lock:{execution_id}` before running the orchestrator.

Queue names:

- main queue: `pipeline:run:jobs`
- retry queue: `pipeline:run:retry:jobs`
- dead-letter queue: `pipeline:run:dead-letter`

## 4. Retry flow

Worker failures are classified as:

- `validation`: `ValueError`, no retry.
- `dependency`: `TimeoutError`, `ConnectionError`, retry.
- `transient`: `RuntimeError`, retry.
- `permanent`: everything else, no retry.

Retry settings:

- `MAX_WORKER_RETRIES = 4`
- delays: `1s`, `5s`, `30s`, `120s`

Retryable failures are written to the delayed Redis sorted set `pipeline:run:retry:jobs`. Before blocking on the main queue, the worker moves due retry payloads back to `pipeline:run:jobs`.

When retry attempts are exhausted, the worker moves the payload to DLQ and then uses fallback `fail_execution()`.

## 5. Cancellation flow

Cancellation is exposed through:

```text
POST /api/v1/executions/{execution_id}/cancel
```

`PipelineExecutionService.cancel_execution()` can cancel executions in pending/running phase statuses. It marks the execution as `cancelled`, records cancellation metrics, and emits `execution_cancelled`.

The orchestrator cooperates with cancellation by checking `PipelineExecutionService.is_cancelled()` before each tracked phase. If cancelled, it raises `PipelineCancelledError`, skips `fail_execution()`, and returns the current cancelled execution.

## 6. Stuck execution recovery

`StuckExecutionService` detects old running executions and marks them failed with:

- `error_code`: `StuckExecutionTimeout`
- `failed_step`: `stuck_execution_detector`
- `failure_category`: `transient`
- `retryable`: `true`

The detector excludes `review_gate` because waiting for human review can be a valid long-running state.

Manual command:

```bash
python scripts/mark_stuck_executions.py --threshold-minutes 30 --limit 100
```

## 7. DLQ inspection

Exhausted retryable jobs are stored in Redis list:

```text
pipeline:run:dead-letter
```

Inspection endpoint:

```text
GET /api/v1/executions/dead-letter
```

Returned fields:

- `execution_id`
- `retry_count`
- `failure_category`
- `dead_letter_reason`
- `dead_lettered_at`

Replay and delete are intentionally not implemented yet.

## 8. Observability endpoints

Runtime snapshot:

```text
GET /api/v1/executions/runtime-snapshot
```

Returns execution status counts, total retries, stuck count, and average execution/evaluation/mutation durations.

Phase analytics:

```text
GET /api/v1/executions/phase-analytics
```

Returns phase-level counts, duration aggregates, retry pressure, and failure rate per `step_name`.

Execution timeline:

```text
GET /api/v1/executions/{execution_id}/timeline
GET /api/v1/executions/{execution_id}/events
```

These expose immutable execution events for a single run.

## 9. Resume and lineage operations

Resume a failed execution by creating a child execution:

```bash
curl -X POST http://localhost:8000/api/v1/executions/{id}/resume \
  -H "Content-Type: application/json" \
  -d '{"reason":"manual retry","resume_from_phase":"document_generation"}'
```

List direct child executions for an execution:

```bash
curl http://localhost:8000/api/v1/executions/{id}/children
```

Inspect the execution family envelope for UI/debugging:

```bash
curl http://localhost:8000/api/v1/executions/{id}/family
```

The family response returns:

- `parent`: the direct parent execution if one exists
- `current`: the requested execution
- `children`: direct child executions created from the requested execution

## 10. Operational commands

Compile changed runtime files:

```bash
python -m py_compile app/services/pipeline_job_queue.py app/workers/pipeline_worker.py app/services/pipeline_execution_service.py
```

Run worker/runtime tests:

```bash
pytest tests/test_pipeline_async.py -q
pytest tests/test_pipeline_execution.py -q
pytest tests/test_execution_events_api.py -q
```

Run stuck execution detector:

```bash
python scripts/mark_stuck_executions.py --threshold-minutes 30 --limit 100
```

Check migration state:

```bash
alembic current
alembic heads
alembic upgrade head
```

## 11. Known limitations

- DLQ is inspection-only. There is no replay/delete API yet.
- Retry is worker-level and Redis-based; it is not a full durable workflow engine.
- Phase retry count is an approximation derived from failed phase rows and execution retry counts.
- Runtime snapshot stuck threshold is fixed at 30 minutes in the observability service.
- No Prometheus exporter, Grafana dashboard, or OpenTelemetry collector is implemented.
- No admin UI exists yet; the current surface is API endpoints and scripts.
- Cancellation is cooperative. A currently executing long-running phase only stops at the next cancellation check.
