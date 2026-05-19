# Execution Lineage Model RFC

Status: draft

## Purpose

Execution replay and resume require an execution graph, not a flat execution list. This RFC defines parent-child semantics, artifact inheritance, evaluation inheritance, review invalidation rules, and lineage querying before implementation.

Hard rule:

```text
Executions are immutable after terminal state.
```

Terminal executions may be referenced by new executions, but not mutated to represent new progress.

## 1. Parent-Child Semantics

Execution lineage is a directed graph.

Example:

```text
execution A
-> resumed as execution B
-> replayed as execution C
```

The parent execution remains unchanged. Child executions reference the parent and carry metadata explaining why they exist.

Minimum lineage fields:

```text
parent_execution_id
replay_reason
replay_phase
replay_trigger
```

Suggested semantics:

- `parent_execution_id`: source execution that caused this child execution.
- `replay_reason`: human-readable explanation.
- `replay_phase`: phase boundary for resume, or `full` for replay.
- `replay_trigger`: `manual`, `admin`, `dlq`, `api`, or future system trigger.

Retry, resume, and replay are distinct:

```text
retry  -> same execution, same attempt chain, automatic
resume -> new execution, continues from failed phase, inherits safe artifacts
replay -> new execution, reruns whole pipeline, may use new inputs
```

## 2. Artifact Inheritance

Artifacts fall into two categories:

```text
reused artifacts
forked artifacts
```

Reuse is allowed when:

- artifact is immutable;
- artifact has a stable id;
- artifact was produced by a completed parent phase;
- artifact is compatible with the child execution pipeline version.

Fork is required when:

- artifact content changes;
- document content changes;
- human edits are applied;
- model output can change;
- the artifact represents user-visible output.

Recommended metadata:

```json
{
  "lineage": {
    "parent_execution_id": "...",
    "reused_artifact_ids": ["..."],
    "forked_artifact_ids": ["..."]
  }
}
```

No child execution should overwrite parent artifacts.

## 3. Evaluation Inheritance

Evaluation snapshots should be treated as immutable evidence for a specific document state and calibration version.

Reuse is allowed when:

- source document is unchanged;
- vacancy snapshot or vacancy interpretation is unchanged;
- calibration version is unchanged;
- scoring model/version is unchanged.

Invalidate and recompute when:

- document content changes;
- vacancy text or vacancy analysis changes;
- scoring rules or calibration version changes;
- human edits change the reviewed artifact;
- resume starts before or at evaluation phase.

Recommended rule:

```text
If document content changes, evaluation snapshots do not carry forward as current truth.
```

Old snapshots remain lineage evidence, but the child execution should create a new snapshot.

## 4. Review Invalidation Rules

Review approval applies to a specific artifact state.

Approval is invalidated when:

- document content changes;
- mutation phase is rerun;
- recommendation application changes visible output;
- evaluation result changes enough to alter review requirement;
- reviewer-approved artifact is forked.

Approval may be preserved only as historical lineage when:

- child execution reuses exactly the same reviewed artifact;
- no content-affecting phase is rerun;
- review policy version is unchanged.

MVP rule:

```text
Do not copy review_completed=True to child executions.
```

Child executions should pass through review gate again if they can change user-visible output.

## 5. Lineage Querying

The API should support viewing an execution family.

Minimum query:

```text
GET /api/v1/executions/{execution_id}/lineage
```

Expected response shape:

```json
{
  "root_execution_id": "...",
  "executions": [
    {
      "execution_id": "...",
      "parent_execution_id": null,
      "status": "failed",
      "replay_phase": null,
      "replay_trigger": null
    },
    {
      "execution_id": "...",
      "parent_execution_id": "...",
      "status": "completed",
      "replay_phase": "mutation",
      "replay_trigger": "manual"
    }
  ]
}
```

Lineage views should make it easy to answer:

- Which execution is the root?
- Which execution produced the current artifact?
- Which artifacts were reused?
- Which artifacts were forked?
- Which review approvals are historical only?

## Data Model Options

Preferred migration-backed columns:

```text
pipeline_executions.parent_execution_id UUID NULL
pipeline_executions.replay_reason TEXT NULL
pipeline_executions.replay_phase VARCHAR NULL
pipeline_executions.replay_trigger VARCHAR NULL
```

MVP metadata fallback:

```json
{
  "lineage": {
    "parent_execution_id": "...",
    "replay_reason": "Dependency outage resolved",
    "replay_phase": "mutation",
    "replay_trigger": "manual",
    "reused_artifact_ids": ["..."],
    "forked_artifact_ids": ["..."]
  }
}
```

Migration-backed fields are preferred before public replay/resume API.

## Operational Implications

Phase analytics should eventually distinguish:

- original executions;
- retry attempts inside the same execution;
- resumed child executions;
- full replay child executions.

Runtime snapshots should count child executions as normal executions but lineage views should prevent confusion when investigating incidents.

DLQ replay should not be added until lineage metadata is available. Otherwise, replayed jobs will be indistinguishable from original work.

## Non-Goals For MVP

- arbitrary graph traversal UI;
- automatic DLQ replay;
- in-place phase replay;
- copying approval state between changed artifacts;
- deterministic replay guarantees;
- event timeline rewriting.

## Implementation Sequence

1. Add lineage columns or a strict metadata contract.
2. Add repository query for parent/child execution family.
3. Add lineage response schema.
4. Add read-only lineage endpoint.
5. Add resume creation service that creates child executions.
6. Teach orchestrator to consume `replay_phase`/resume metadata.
7. Update phase analytics to expose original/resumed execution distinction.
8. Consider DLQ replay only after lineage is visible.
