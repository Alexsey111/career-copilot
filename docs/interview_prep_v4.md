# Interview Prep v4

This note captures the current interview preparation contract after the mock interview stabilization pass.

## Architecture

- `app.services.interview_preparation_service.InterviewPreparationService` owns mock interview lifecycle, deterministic answer evaluation, summary assembly, and advisory generation.
- `app.api.routes.interviews` exposes the HTTP contract and keeps the route layer thin.
- `frontend/streamlit/flows/document_application_flow.py` renders a thin mock interview surface and never mutates backend state directly.
- `app.repositories.interview_session_repository.InterviewSessionRepository` persists sessions and attempts.

## Session lifecycle

Mock interview follows a forward-only lifecycle:

1. `draft`
2. `in_progress`
3. `completed`

Guardrails:

- `mock/start` is rejected after completion.
- `mock/current` requires a started mock session.
- `mock/answer` rejects invalid pointers.
- `mock/answer` is rejected after completion.

## API contracts

### Start

`POST /api/v1/interviews/sessions/{session_id}/mock/start`

Response:

- `status`
- `mode`
- `current_question_index`
- `completed_at`

### Current question

`GET /api/v1/interviews/sessions/{session_id}/mock/current`

Response:

- `question_index`
- `question`
- `progress`

### Submit answer

`POST /api/v1/interviews/sessions/{session_id}/mock/answer`

Response:

- `session`
- `evaluation`
- `advisory`
- `completed`
- `next_question`
- `progress`

### Summary

`GET /api/v1/interviews/sessions/{session_id}/mock/summary`

Response:

- `session`
- `progress`
- `readiness_score`
- `competency_readiness`
- `weak_competencies`
- `attempt_count`

## Deterministic vs advisory logic

Deterministic evaluation:

- runs on every submitted answer
- produces score and feedback
- updates persisted session state

Advisory logic:

- is optional and request-driven
- returns suggested revisions and coaching hints
- does not overwrite the saved answer

## Observability notes

- `attempt_count` now exposes a stable smoke signal for future analytics.
- `weak_competencies` mirrors the dashboard notion of weak areas and is safe to reuse for reporting.
- The mock summary endpoint is the canonical read model for completion state.
