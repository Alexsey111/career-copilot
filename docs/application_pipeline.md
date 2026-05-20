# Application Pipeline

This document fixes the current application pipeline contract for backend, UI, and future analytics work.

## Statuses / State Machine

Canonical status values:

- `draft`
- `ready`
- `applied`
- `screening`
- `interview`
- `offer`
- `rejected`
- `withdrawn`

Rules:

- `applied` is the canonical submission status.
- Status transitions are owned by the backend.
- The frontend only renders backend workflow metadata.

## Submit Boundary

Submitting an application is a dedicated backend action:

- `POST /applications/{application_id}/submit`

The submit boundary is separate from generic status updates.
It records the manual submission event, sets `applied_at`, and keeps the safety gate in the backend.

## Safety Gate

Before submit, the backend checks whether the application is safe to submit.

If the gate blocks submission, the API returns a conflict response with blockers and warnings.
This keeps human-in-the-loop behavior explicit and prevents accidental submission.

## Workflow API

The backend owns the workflow graph and exposes it through:

- `GET /applications/{application_id}/workflow`

The response tells the UI:

- current status;
- allowed transitions;
- whether submit is currently allowed;
- whether the state is final.

## Status History vs Activity Log

These are separate views with different jobs:

- `timeline` / status history: state transitions only
- `activity-log`: all application events

Use status history when you need to understand how the state changed.
Use activity log when you need the operational story of the pipeline.

## Canonical Event Types

The canonical event taxonomy is defined in `app/domain/application_events.py`.

Current event types:

- `application_created`
- `application_ready`
- `application_applied`
- `application_status_changed`
- `document_attached`
- `note_added`
- `interview_session_created`
- `outcome_recorded`
- `external_link_added`

This taxonomy is backend-owned and should not be extended ad hoc in the UI or tests.

## Event Meta Contract

Event `meta_json` is structured JSON with documented shapes.

### `application_created`

```json
{
  "vacancy_id": "...",
  "resume_document_id": "...",
  "cover_letter_document_id": "..."
}
```

### `application_status_changed`

```json
{
  "previous_status": "ready",
  "new_status": "screening",
  "source": "manual"
}
```

### `application_applied`

```json
{
  "source": "manual",
  "external_link": "...",
  "applied_at": "2026-05-20T10:22:00+00:00"
}
```

The backend builds these payloads through helpers in `app/domain/application_event_meta.py`.

## Frontend Responsibility

The Streamlit frontend should:

- render backend workflow metadata;
- show status history and activity log;
- use `source`, not legacy `channel`;
- avoid embedding state-machine logic;
- avoid inventing event types or event metadata shapes.

## Why This Matters

This contract gives us a stable base for:

- funnel analytics;
- time-to-offer analysis;
- interview conversion tracking;
- readiness correlation;
- resume version effectiveness;
- reminders and automation later.
