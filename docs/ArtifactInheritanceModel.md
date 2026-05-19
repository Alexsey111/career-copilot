# Artifact Inheritance Model

## 1. Why define this first

Resume and replay introduce execution lineage, but lineage alone is not enough. The system also needs a clear rule for which artifacts stay attached to a historical execution, which artifacts can be reused by a child execution, and which artifacts must be regenerated.

Without an explicit artifact inheritance model, the platform will quickly drift into ambiguity:

- which artifacts belong to which execution
- which artifacts are safe to reuse after resume
- which artifacts should be invalidated when inputs change

That ambiguity will break analytics, replay semantics, and review provenance.

This document is intentionally short. Its goal is to define the minimum artifact inheritance contract before the runtime grows more lineage-aware behavior.

## 2. Artifact categories

Artifacts should be divided into two categories.

Immutable artifacts:

- evaluation snapshots
- review decisions
- impact measurements

These represent historical evidence produced in a specific execution context. They should remain attached to the execution that produced them and should not be silently rewritten to represent later work.

Regeneratable artifacts:

- tailored resumes
- cover letters
- recommendations

These are user-facing or execution-derived outputs that may change when the execution is resumed, replayed, or run against updated inputs.

## 3. Inheritance policy

Resume behavior:

- inherits immutable artifacts by reference when they are still valid
- regenerates mutable artifacts in the child execution

This means a resumed child execution can point to lineage-relevant historical artifacts, but it should produce its own fresh tailored outputs instead of reusing old mutable results as if they were newly created.

The default rule should be conservative:

- preserve immutable artifacts as lineage evidence
- regenerate user-visible or decision-driving outputs unless a rule explicitly says reuse is safe

## 4. Invalidations

Inheritance must support explicit invalidation rules.

Example:

- new vacancy version -> invalidate evaluation snapshot

Other invalidation triggers will likely be added later, but the model should assume that immutable-by-history does not always mean reusable-by-child. Some historical artifacts remain valuable as provenance while still being invalid for operational reuse.

This distinction matters:

- historical evidence can remain visible in lineage
- operational execution may still need a fresh artifact

## 5. Lineage visibility

Artifacts should carry lineage visibility through:

- `artifact_source_execution_id`

This field answers a basic but critical question:

- which execution originally produced this artifact

That visibility is necessary for debugging, auditability, and later UI surfaces that need to explain whether an artifact was inherited, regenerated, or produced in the current run.

## 6. Why this RFC matters

If artifact inheritance is left implicit, the platform will accumulate contradictory assumptions:

- analytics will count reused and regenerated artifacts incorrectly
- replay and resume semantics will become inconsistent
- review provenance will be lost or misattributed

The purpose of this RFC is to prevent that chaos by establishing a small, durable contract before more implementation depends on undocumented behavior.
