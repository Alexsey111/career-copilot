from __future__ import annotations

import pytest


API_PREFIX = "/api/v1"


@pytest.mark.asyncio
async def test_execution_events_api_returns_timeline(client, test_user):
    create_response = await client.post(
        f"{API_PREFIX}/career-copilot/run",
        json={
            "user_id": str(test_user.id),
            "pipeline_version": "v1.0",
        },
    )
    assert create_response.status_code == 201
    execution_id = create_response.json()["id"]

    events_response = await client.get(f"{API_PREFIX}/executions/{execution_id}/events")
    assert events_response.status_code == 200

    events = events_response.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "execution_started"
    assert "created_at" in events[0]
