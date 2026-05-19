# Execution Replay and Resume RFC

Status: draft

## Purpose

This RFC defines replay and resume semantics before implementation. Replay is a workflow semantics layer, not just another retry button. The goal is to avoid mutating historical executions in ways that break lineage, auditability, human review guarantees, or artifact consistency.

Current recommendation for MVP:

```text
Do not implement true replay.
Implement resume from failed phase by creating a new execution that references the parent execution.
```

This gives the system execution lineage instead of rewriting existing execution history.

Hard rule:

```text
Executions are immutable after terminal state.
```

Terminal states:

```text
completed
failed
cancelled
```

Once an execution reaches a terminal state, it must never be mutated to represent replay or resume progress. Replay and resume must create a new execution, preserve lineage, and record replay metadata.

## Terminology

### Retry

```text
same execution
same attempt chain
automatic
```

Retry is a worker/runtime concern. It handles transient or dependency failures before the execution reaches a final terminal outcome. Retry should not create a separate execution.

### Resume

```text
new execution
continues from failed phase
inherits safe artifacts
```

Resume is an explicit workflow action. It creates a child execution and starts from a safe phase boundary using immutable artifacts from the parent execution.

### Replay

```text
new execution
reruns whole pipeline
may use new inputs
```

Replay is a workflow action that starts a new execution from the beginning. It may use original inputs or changed inputs, but it must not mutate the original execution.

These terms are intentionally separate. Collapsing retry, resume, and replay into one concept will make APIs inconsistent, analytics ambiguous, and observability noisy.

## 1. Replay Semantics

### Full Replay

Full replay means running the whole pipeline again from the original inputs.

Open questions:

- Should it reuse the same uploaded document and vacancy?
- Should it reuse the same calibration/version settings?
- Should it inherit prior recommendations?
- Should old generated artifacts remain linked to the new run?

Risk:

- A full replay can produce different outputs if prompts, models, calibration rules, vacancy data, or profile data changed.

MVP decision:

- Full replay is out of scope.

### Phase Replay

Phase replay means rerunning one named phase, such as `mutation` or `impact_measurement`.

Open questions:

- Can a phase run safely without rerunning previous phases?
- Are input artifacts still valid?
- Does the phase mutate shared state?
- Does the phase depend on current database state or prior immutable snapshots?

Risk:

- Phase replay can create partial state that disagrees with execution events and existing artifacts.

MVP decision:

- Direct phase replay inside the same execution is out of scope.

### Resume From Failed Phase

Resume from failed phase means starting from the failed phase boundary using known previous artifacts.

Recommended MVP semantics:

```text
parent execution failed
-> user/admin requests resume
-> system creates new execution
-> new execution references parent execution
-> new execution starts from the failed phase when safe
```

The parent execution remains immutable and failed.

## 2. Artifact Semantics

Artifacts must be treated as lineage-bearing data, not temporary scratch files.

### Reuse Artifacts

Reuse means the child execution consumes artifacts produced by the parent execution.

Allowed when:

- Artifact is immutable.
- Artifact has a stable id.
- Artifact was produced by a completed phase.
- Artifact is still compatible with current pipeline version.

Example:

- Initial evaluation snapshot can be reused by a child execution resuming at recommendation generation.

### Fork Artifacts

Fork means the child execution creates a new artifact derived from a parent artifact.

Required when:

- The artifact is edited.
- The artifact is mutable.
- The phase produces a new document version.
- The resume path can produce different outputs.

Example:

- Mutated resume document should be a new `DocumentVersion`, not an overwrite.

### Immutable Lineage

Every resumed execution should preserve:

- parent execution id
- source artifact ids
- new artifact ids
- resume phase
- resume reason

MVP data model likely needs:

```text
pipeline_executions.parent_execution_id
pipeline_executions.replay_phase
pipeline_executions.replay_reason
pipeline_executions.replay_trigger
```

Or equivalent fields in `metadata_json` for a first cut.

## 3. Human Review Semantics

Human review makes replay more sensitive because approval may only apply to a specific artifact state.

Questions:

- Can a reviewed execution be resumed?
- Does a new mutation invalidate approval?
- Does reusing a reviewed artifact carry over approval?
- Should review status be copied or reset?

Recommended rule:

```text
Any resume that changes document content invalidates prior approval.
```

MVP behavior:

- Do not copy `review_completed=True` to resumed child executions.
- Preserve parent review id as lineage only.
- Require a new review gate if resumed phases can change user-visible output.

## 4. Cancellation Semantics

Cancelled executions should be treated as intentionally stopped, not failed.

Questions:

- Can cancelled execution be resumed?
- Should resume preserve cancellation reason?
- Is cancellation a user intent that blocks automatic resume?

Recommended rule:

```text
Cancelled executions are not automatically replayable.
Manual resume may create a new child execution if requested explicitly.
```

MVP behavior:

- No automatic resume from cancelled.
- Admin/user initiated resume can create a new execution with `parent_execution_id`.
- Cancellation event remains immutable on the parent.

## 5. Idempotency Semantics

Replay/resume must not reuse idempotency semantics blindly.

Options:

- same execution id: unsafe, mutates history.
- same idempotency key: unsafe, can collapse distinct resume attempts.
- new execution id with parent lineage: safest.

Recommended MVP:

```text
Every resume creates a new execution id.
The child execution references the parent execution id.
The idempotency key should be resume-specific.
```

Possible resume idempotency key:

```text
resume:{parent_execution_id}:{resume_from_step}:{request_id}
```

For API safety, caller-provided idempotency key should still be accepted, but scoped to the resume request.

## Recommended MVP

Implement only:

```text
resume from failed phase
-> create new execution
-> reference parent execution
-> reuse immutable completed-phase artifacts
-> fork any newly produced artifacts
-> do not mutate parent execution
```

Do not implement:

- true full replay
- in-place phase replay
- automatic replay from DLQ
- automatic replay from cancelled executions
- copying review approval to changed artifacts

## Proposed API Shape

Draft endpoint:

```text
POST /api/v1/executions/{execution_id}/resume
```

Request:

```json
{
  "resume_from_step": "mutation",
  "reason": "Dependency outage resolved",
  "idempotency_key": "resume-2026-05-19-001"
}
```

Response:

```json
{
  "parent_execution_id": "...",
  "execution_id": "...",
  "status": "queued",
  "resume_from_step": "mutation"
}
```

## Proposed Data Model

Preferred:

```text
pipeline_executions.parent_execution_id UUID NULL
pipeline_executions.resume_from_step VARCHAR NULL
pipeline_executions.resume_reason TEXT NULL
```

Alternative MVP without migration:

```json
{
  "resume": {
    "parent_execution_id": "...",
    "resume_from_step": "mutation",
    "reason": "Dependency outage resolved"
  }
}
```

stored in `metadata_json` or `metrics_json`.

Migration-backed fields are preferred before public API use.

## Safety Rules

- Parent execution is immutable.
- Executions in `completed`, `failed`, or `cancelled` state must never be mutated for replay/resume.
- Child execution must get a new execution id.
- New output artifacts must not overwrite parent artifacts.
- Resume must record source artifact ids.
- Resume must record pipeline version and calibration version.
- Review approval is not copied if resumed phases can change document content.
- DLQ inspection must stay separate from replay until replay semantics are implemented.
- In-place phase replay is forbidden for MVP.

## Open Questions

- Which phase boundaries are safe resume points?
- Which artifacts are required for each phase?
- How should parent/child executions appear in timeline APIs?
- Should runtime snapshot count resumed executions separately?
- Should phase analytics distinguish original runs from resume runs?
- Should resume require admin-only permissions?
- Should child execution inherit correlation id or create a new one linked to parent?

## Non-Goals For MVP

- Full workflow engine.
- Deterministic replay guarantee.
- Replay of arbitrary historical executions.
- Replay from arbitrary event timeline offsets.
- Automatic DLQ replay.
- Admin UI for replay controls.

## Implementation Sequence

Recommended order:

1. Add explicit lineage fields or metadata contract.
2. Define safe phase resume boundaries and required artifacts.
3. Add resume request/response schemas.
4. Add service method that creates a child execution.
5. Queue child execution with resume metadata.
6. Teach orchestrator to start from selected phase using existing artifacts.
7. Add timeline visibility for parent/child relationship.
8. Only then consider DLQ replay helpers.
