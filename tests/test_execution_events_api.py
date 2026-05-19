from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from uuid import UUID, uuid4

from app.api.routes import executions
from app.models import (
    DocumentVersion,
    ImpactMeasurement,
    PipelineExecution,
    Recommendation,
    Vacancy,
    VacancyAnalysis,
)
from app.repositories.pipeline_execution_repository import PhaseRuntimeAggregate
from app.services.document_mutation_service import DocumentMutationService


API_PREFIX = "/api/v1"


async def _prepare_profile(client) -> None:
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

    structured_response = await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    assert structured_response.status_code == 200, structured_response.text

    achievements_response = await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )
    assert achievements_response.status_code == 200, achievements_response.text


async def _create_analyzed_vacancy(client) -> str:
    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "description_raw": (
                "Требования:\n"
                "- Python\n"
                "- FastAPI\n"
                "- PostgreSQL\n"
                "\n"
                "Будет плюсом:\n"
                "- Redis\n"
                "- Docker\n"
            ),
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy_id = vacancy_response.json()["vacancy_id"]

    analysis_response = await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze",
    )
    assert analysis_response.status_code == 200, analysis_response.text

    return vacancy_id


async def _create_failed_execution(client, db_session, test_user) -> tuple[PipelineExecution, str, str]:
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    document_id = resume_response.json()["document_id"]

    execution = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="failed",
        pipeline_version="v1.0",
        calibration_version="calib-v1",
        failed_at=datetime.now(timezone.utc),
        failed_step="document_generation",
        last_error="boom",
        lineage_metadata_json={},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution, document_id, vacancy_id


async def _attach_evaluation_snapshot(
    db_session,
    *,
    execution: PipelineExecution,
    vacancy_id: str,
    created_at: datetime | None = None,
) -> VacancyAnalysis:
    snapshot = VacancyAnalysis(
        id=uuid4(),
        vacancy_id=UUID(vacancy_id),
        must_have_json=[],
        nice_to_have_json=[],
        keywords_json=[],
        gaps_json=[],
        strengths_json=[],
        match_score=85,
        analysis_version="v1",
    )
    if created_at is not None:
        snapshot.created_at = created_at
        snapshot.updated_at = created_at
    db_session.add(snapshot)
    await db_session.flush()
    execution.evaluation_snapshot_id = snapshot.id
    await db_session.commit()
    await db_session.refresh(execution)
    return snapshot


@pytest.mark.asyncio
async def test_execution_runtime_snapshot_api_returns_operational_counts(client):
    response = await client.get(f"{API_PREFIX}/executions/runtime-snapshot")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["running_count"] >= 0
    assert payload["completed_count"] >= 0
    assert payload["failed_count"] >= 0
    assert payload["cancelled_count"] >= 0
    assert payload["retry_total"] >= 0
    assert payload["stuck_count"] >= 0
    assert payload["avg_execution_duration_ms"] >= 0.0
    assert payload["avg_evaluation_duration_ms"] >= 0.0
    assert payload["avg_mutation_duration_ms"] >= 0.0


@pytest.mark.asyncio
async def test_execution_dead_letter_api_returns_inspection_fields(client, monkeypatch):
    class FakeQueue:
        async def get_dead_letter_jobs(self, *, limit: int = 100):
            return [
                {
                    "execution_id": "execution-1",
                    "retry_count": "4",
                    "failure_category": "transient",
                    "dead_letter_reason": "Worker retries exhausted",
                    "dead_lettered_at": "2026-05-19T12:00:00+00:00",
                    "user_id": "hidden-from-response",
                }
            ][:limit]

    monkeypatch.setattr(executions, "RedisPipelineJobQueue", FakeQueue)

    response = await client.get(f"{API_PREFIX}/executions/dead-letter")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == [
        {
            "execution_id": "execution-1",
            "retry_count": 4,
            "failure_category": "transient",
            "dead_letter_reason": "Worker retries exhausted",
            "dead_lettered_at": "2026-05-19T12:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_execution_phase_analytics_api_returns_phase_metrics(client, monkeypatch):
    async def get_phase_runtime_aggregates(self, session, *, limit: int = 100):
        return [
            PhaseRuntimeAggregate(
                step_name="mutation",
                total_count=10,
                completed_count=9,
                failed_count=1,
                avg_duration_ms=1420.0,
                max_duration_ms=3000.0,
                retry_count=2,
            )
        ][:limit]

    monkeypatch.setattr(
        executions.PipelineExecutionRepository,
        "get_phase_runtime_aggregates",
        get_phase_runtime_aggregates,
    )

    response = await client.get(f"{API_PREFIX}/executions/phase-analytics")

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "step_name": "mutation",
            "total_count": 10,
            "completed_count": 9,
            "failed_count": 1,
            "avg_duration_ms": 1420.0,
            "max_duration_ms": 3000.0,
            "retry_count": 2,
            "failure_rate": 0.1,
        }
    ]


@pytest.mark.asyncio
async def test_resume_execution_creates_child_execution(client, db_session, test_user, monkeypatch):
    parent_execution, _, _ = await _create_failed_execution(client, db_session, test_user)
    captured: dict[str, object] = {}

    class FakeQueue:
        async def enqueue_pipeline_run(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(executions, "RedisPipelineJobQueue", FakeQueue)

    response = await client.post(
        f"{API_PREFIX}/executions/{parent_execution.id}/resume",
        json={
            "reason": "retry after incident",
            "resume_from_phase": "document_generation",
        },
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    child_execution_id = UUID(payload["child_execution_id"])
    assert payload["parent_execution_id"] == str(parent_execution.id)
    assert payload["lineage_kind"] == "resume"
    assert payload["status"] == "queued"

    child_execution = await db_session.get(PipelineExecution, child_execution_id)
    assert child_execution is not None
    assert child_execution.parent_execution_id == parent_execution.id
    assert child_execution.lineage_kind == "resume"
    assert child_execution.lineage_reason == "retry after incident"
    assert child_execution.lineage_metadata_json == {
        "resume_from_phase": "document_generation",
        "source_execution_status": "failed",
    }
    assert child_execution.document_id == parent_execution.document_id
    assert child_execution.vacancy_id == parent_execution.vacancy_id
    assert child_execution.pipeline_version == parent_execution.pipeline_version
    assert child_execution.calibration_version == parent_execution.calibration_version
    assert captured["execution_id"] == child_execution_id


@pytest.mark.asyncio
async def test_resume_execution_rejects_non_failed_execution(client, db_session, test_user):
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    document_id = resume_response.json()["document_id"]

    execution = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="completed",
        pipeline_version="v1.0",
        lineage_metadata_json={},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    db_session.add(execution)
    await db_session.commit()

    response = await client.post(
        f"{API_PREFIX}/executions/{execution.id}/resume",
        json={"reason": "should fail"},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "only failed executions can be resumed"


@pytest.mark.asyncio
async def test_resume_execution_queues_existing_child_execution_id(client, db_session, test_user, monkeypatch):
    parent_execution, _, _ = await _create_failed_execution(client, db_session, test_user)
    captured_execution_ids: list[UUID] = []

    class FakeQueue:
        async def enqueue_pipeline_run(self, **kwargs):
            captured_execution_ids.append(kwargs["execution_id"])

    monkeypatch.setattr(executions, "RedisPipelineJobQueue", FakeQueue)

    response = await client.post(
        f"{API_PREFIX}/executions/{parent_execution.id}/resume",
        json={"resume_from_phase": "document_generation"},
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert captured_execution_ids == [UUID(payload["child_execution_id"])]


@pytest.mark.asyncio
async def test_resume_execution_inherits_evaluation_snapshot_reference(
    client,
    db_session,
    test_user,
    monkeypatch,
):
    parent_execution, _, vacancy_id = await _create_failed_execution(client, db_session, test_user)
    snapshot = await _attach_evaluation_snapshot(
        db_session,
        execution=parent_execution,
        vacancy_id=vacancy_id,
        created_at=datetime.now(timezone.utc),
    )

    class FakeQueue:
        async def enqueue_pipeline_run(self, **kwargs):
            return None

    monkeypatch.setattr(executions, "RedisPipelineJobQueue", FakeQueue)

    response = await client.post(
        f"{API_PREFIX}/executions/{parent_execution.id}/resume",
        json={"resume_from_phase": "document_evaluation"},
    )

    assert response.status_code == 202, response.text
    child_execution = await db_session.get(
        PipelineExecution,
        UUID(response.json()["child_execution_id"]),
    )
    assert child_execution is not None
    assert child_execution.evaluation_snapshot_id == snapshot.id
    assert child_execution.lineage_metadata_json["inherited_artifacts"] == {
        "evaluation_snapshot_id": str(snapshot.id),
    }


@pytest.mark.asyncio
async def test_resume_execution_does_not_inherit_snapshot_when_vacancy_changed(
    client,
    db_session,
    test_user,
    monkeypatch,
):
    parent_execution, _, vacancy_id = await _create_failed_execution(client, db_session, test_user)
    snapshot = await _attach_evaluation_snapshot(
        db_session,
        execution=parent_execution,
        vacancy_id=vacancy_id,
        created_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
    )
    vacancy = await db_session.get(Vacancy, UUID(vacancy_id))
    assert vacancy is not None
    vacancy.updated_at = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    await db_session.commit()

    class FakeQueue:
        async def enqueue_pipeline_run(self, **kwargs):
            return None

    monkeypatch.setattr(executions, "RedisPipelineJobQueue", FakeQueue)

    response = await client.post(
        f"{API_PREFIX}/executions/{parent_execution.id}/resume",
        json={"resume_from_phase": "document_evaluation"},
    )

    assert response.status_code == 202, response.text
    child_execution = await db_session.get(
        PipelineExecution,
        UUID(response.json()["child_execution_id"]),
    )
    assert child_execution is not None
    assert parent_execution.evaluation_snapshot_id == snapshot.id
    assert child_execution.evaluation_snapshot_id is None
    assert "inherited_artifacts" not in child_execution.lineage_metadata_json


@pytest.mark.asyncio
async def test_get_child_executions_returns_lineage_family(client, db_session, test_user):
    parent_execution, document_id, vacancy_id = await _create_failed_execution(client, db_session, test_user)

    first_child = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="failed",
        pipeline_version="v1.0",
        calibration_version="calib-v1",
        parent_execution_id=parent_execution.id,
        lineage_kind="resume",
        lineage_reason="first retry",
        lineage_metadata_json={"resume_from_phase": "document_generation"},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    second_child = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="pending",
        pipeline_version="v1.0",
        calibration_version="calib-v1",
        parent_execution_id=parent_execution.id,
        lineage_kind="replay",
        lineage_reason="manual replay",
        lineage_metadata_json={"resume_from_phase": "coverage_mapping"},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    unrelated_execution = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="pending",
        pipeline_version="v1.0",
        parent_execution_id=None,
        lineage_metadata_json={},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    db_session.add_all([first_child, second_child, unrelated_execution])
    await db_session.commit()

    response = await client.get(f"{API_PREFIX}/executions/{parent_execution.id}/children")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload] == [str(first_child.id), str(second_child.id)]
    assert all(item["parent_execution_id"] == str(parent_execution.id) for item in payload)
    assert payload[0]["lineage_kind"] == "resume"
    assert payload[0]["lineage_reason"] == "first retry"
    assert payload[0]["lineage_metadata_json"] == {"resume_from_phase": "document_generation"}
    assert payload[1]["lineage_kind"] == "replay"


@pytest.mark.asyncio
async def test_get_execution_family_returns_parent_current_and_children(client, db_session, test_user):
    parent_execution, document_id, vacancy_id = await _create_failed_execution(client, db_session, test_user)

    current_execution = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="running",
        pipeline_version="v1.0",
        calibration_version="calib-v1",
        parent_execution_id=parent_execution.id,
        lineage_kind="resume",
        lineage_reason="resume current",
        lineage_metadata_json={"resume_from_phase": "coverage_mapping"},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    child_execution = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="pending",
        pipeline_version="v1.0",
        calibration_version="calib-v1",
        parent_execution_id=current_execution.id,
        lineage_kind="replay",
        lineage_reason="child replay",
        lineage_metadata_json={"resume_from_phase": "document_evaluation"},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    db_session.add_all([current_execution, child_execution])
    await db_session.commit()

    response = await client.get(f"{API_PREFIX}/executions/{current_execution.id}/family")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["parent"]["id"] == str(parent_execution.id)
    assert payload["current"]["id"] == str(current_execution.id)
    assert payload["current"]["parent_execution_id"] == str(parent_execution.id)
    assert [item["id"] for item in payload["children"]] == [str(child_execution.id)]
    assert payload["children"][0]["parent_execution_id"] == str(current_execution.id)


@pytest.mark.asyncio
async def test_get_execution_lineage_graph_returns_parent_children_and_inherited_artifacts(
    client,
    db_session,
    test_user,
):
    parent_execution, document_id, vacancy_id = await _create_failed_execution(client, db_session, test_user)
    current_execution = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="running",
        pipeline_version="v1.0",
        calibration_version="calib-v1",
        parent_execution_id=parent_execution.id,
        lineage_kind="resume",
        lineage_reason="resume current",
        lineage_metadata_json={
            "resume_from_phase": "document_evaluation",
            "inherited_artifacts": {
                "evaluation_snapshot_id": str(uuid4()),
            },
        },
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    first_child = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="pending",
        pipeline_version="v1.0",
        parent_execution_id=current_execution.id,
        lineage_metadata_json={},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    second_child = PipelineExecution(
        id=uuid4(),
        user_id=test_user.id,
        document_id=UUID(document_id),
        vacancy_id=UUID(vacancy_id),
        profile_id=None,
        status="failed",
        pipeline_version="v1.0",
        parent_execution_id=current_execution.id,
        lineage_metadata_json={},
        artifacts_json={},
        metrics_json={},
        output_artifact_ids=[],
        input_params={},
        metadata_json={},
    )
    db_session.add_all([current_execution, first_child, second_child])
    await db_session.commit()

    response = await client.get(f"{API_PREFIX}/executions/{current_execution.id}/lineage-graph")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["execution_id"] == str(current_execution.id)
    assert payload["parent_execution_id"] == str(parent_execution.id)
    assert payload["children"] == [str(first_child.id), str(second_child.id)]
    assert payload["inherited_artifacts"] == current_execution.lineage_metadata_json["inherited_artifacts"]


@pytest.mark.asyncio
async def test_get_execution_lineage_graph_returns_404_for_missing_execution(client):
    response = await client.get(f"{API_PREFIX}/executions/{uuid4()}/lineage-graph")

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "execution not found"


@pytest.mark.asyncio
async def test_get_execution_family_returns_404_for_missing_execution(client):
    response = await client.get(f"{API_PREFIX}/executions/{uuid4()}/family")

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "execution not found"


@pytest.mark.asyncio
async def test_get_child_executions_returns_404_for_missing_parent(client):
    response = await client.get(f"{API_PREFIX}/executions/{uuid4()}/children")

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "execution not found"


@pytest.mark.asyncio
async def test_execution_events_api_returns_timeline(client, db_session, test_user):
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    document_id = resume_response.json()["document_id"]

    create_response = await client.post(
        f"{API_PREFIX}/career-copilot/run",
        json={
            "user_id": str(test_user.id),
            "document_id": document_id,
            "vacancy_id": vacancy_id,
            "pipeline_version": "v1.0",
        },
    )
    assert create_response.status_code == 201, create_response.text
    run_payload = create_response.json()
    execution_id = UUID(run_payload["id"])
    recommendation_id = run_payload["artifacts_json"]["recommendation_id"]
    mutated_document_id = UUID(run_payload["artifacts_json"]["mutated_document_id"])

    recommendation_rows = (
        await db_session.execute(
            select(Recommendation).where(Recommendation.execution_id == execution_id)
        )
    ).scalars().all()
    assert recommendation_rows, "Expected persistent recommendations for the execution"
    assert any(str(row.id) == recommendation_id for row in recommendation_rows)

    impact_row = (
        await db_session.execute(
            select(ImpactMeasurement).where(ImpactMeasurement.recommendation_id == recommendation_id)
        )
    ).scalar_one_or_none()
    assert impact_row is not None

    mutated_document = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.id == mutated_document_id)
        )
    ).scalar_one_or_none()
    assert mutated_document is not None
    assert str(mutated_document.source_recommendation_id) == recommendation_id
    mutation_history = mutated_document.content_json.get("mutation_history", [])
    assert mutation_history, "Expected mutation history in mutated document"
    assert mutation_history[-1]["source_recommendation_id"] == recommendation_id
    assert recommendation_id in mutation_history[-1]["reason"]

    events_response = await client.get(f"{API_PREFIX}/executions/{execution_id}/events")
    assert events_response.status_code == 200

    events = events_response.json()
    assert len(events) >= 3
    assert events[0]["event_type"] == "execution_started"
    assert any(event["event_type"] == "evaluation_completed" for event in events)
    assert any(event["event_type"] == "execution_completed" for event in events)
    assert events[-1]["event_type"] == "step_completed"
    assert "created_at" in events[0]
    assert all(event["payload_json"]["trace_id"] == str(execution_id) for event in events)
    assert all(event["payload_json"]["correlation_id"] for event in events)

    timeline_response = await client.get(f"{API_PREFIX}/executions/{execution_id}/timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert timeline[0]["type"] == "execution_started"
    assert any(item["type"] == "evaluation_completed" and item["score"] is not None for item in timeline)
    assert any(item["type"] == "execution_completed" for item in timeline)
    assert timeline[-1]["type"] == "step_completed"
    assert "timestamp" in timeline[0]
    assert all(item["trace_id"] == str(execution_id) for item in timeline)
    assert all(item["correlation_id"] for item in timeline)


@pytest.mark.asyncio
async def test_execution_failure_is_recorded_and_partial_mutation_rolls_back(
    client,
    db_session,
    test_user,
    monkeypatch,
):
    user_id = test_user.id
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    document_id = resume_response.json()["document_id"]

    async def boom(*args, **kwargs):
        raise RuntimeError("mutation boom")

    monkeypatch.setattr(DocumentMutationService, "_add_mutation_metadata", boom)

    create_response = await client.post(
        f"{API_PREFIX}/career-copilot/run",
        json={
            "user_id": str(test_user.id),
            "document_id": document_id,
            "vacancy_id": vacancy_id,
            "pipeline_version": "v1.0",
        },
    )
    assert create_response.status_code == 500, create_response.text

    execution = (
        await db_session.execute(
            select(PipelineExecution)
            .where(PipelineExecution.user_id == user_id)
            .order_by(PipelineExecution.created_at.desc())
        )
    ).scalars().first()
    assert execution is not None
    assert execution.status == "failed"
    assert execution.failed_step == "mutation"
    assert execution.retry_count == 1
    assert "mutation boom" in (execution.last_error or "")

    events_response = await client.get(f"{API_PREFIX}/executions/{execution.id}/events")
    assert events_response.status_code == 200, events_response.text
    events = events_response.json()
    assert any(event["event_type"] == "execution_failed" for event in events)
    failed_event = next(event for event in events if event["event_type"] == "execution_failed")
    assert failed_event["payload_json"]["failed_step"] == "mutation"
    assert failed_event["payload_json"]["retry_count"] == 1
    assert "mutation boom" in failed_event["payload_json"]["message"]
    assert failed_event["payload_json"]["trace_id"] == str(execution.id)
    assert failed_event["payload_json"]["correlation_id"]

    mutated_document_rows = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.derived_from_id == UUID(document_id))
        )
    ).scalars().all()
    assert mutated_document_rows == []


@pytest.mark.asyncio
async def test_pipeline_run_is_idempotent_for_same_key(client, db_session, test_user):
    await _prepare_profile(client)
    vacancy_id = await _create_analyzed_vacancy(client)

    resume_response = await client.post(
        f"{API_PREFIX}/documents/resumes/generate",
        json={"vacancy_id": vacancy_id},
    )
    assert resume_response.status_code == 200, resume_response.text
    document_id = resume_response.json()["document_id"]

    idempotency_key = "run-2026-05-18"

    first_response = await client.post(
        f"{API_PREFIX}/career-copilot/run",
        json={
            "user_id": str(test_user.id),
            "document_id": document_id,
            "vacancy_id": vacancy_id,
            "pipeline_version": "v1.0",
            "idempotency_key": idempotency_key,
        },
    )
    assert first_response.status_code == 201, first_response.text
    first_payload = first_response.json()

    first_mutations = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.derived_from_id == UUID(document_id))
        )
    ).scalars().all()
    assert len(first_mutations) == 1

    second_response = await client.post(
        f"{API_PREFIX}/career-copilot/run",
        json={
            "user_id": str(test_user.id),
            "document_id": document_id,
            "vacancy_id": vacancy_id,
            "pipeline_version": "v1.0",
            "idempotency_key": idempotency_key,
        },
    )
    assert second_response.status_code == 201, second_response.text
    second_payload = second_response.json()

    assert second_payload["id"] == first_payload["id"]
    assert second_payload["artifacts_json"]["mutated_document_id"] == first_payload["artifacts_json"]["mutated_document_id"]

    second_mutations = (
        await db_session.execute(
            select(DocumentVersion).where(DocumentVersion.derived_from_id == UUID(document_id))
        )
    ).scalars().all()
    assert len(second_mutations) == 1
