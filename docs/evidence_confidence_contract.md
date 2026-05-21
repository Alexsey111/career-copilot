# Evidence Confidence Contract

## Purpose

Evidence confidence normalizes how the product describes trust in generated documents, interview prep output, and review summaries.

This is a deterministic baseline, not a machine-learned score.

## Deterministic Baseline

- `confirmed` + `strong` evidence + complete STAR -> `high`
- `confirmed` + partial STAR or medium evidence -> `medium`
- `partial` or `unverified` -> `low`
- `gap-risk` -> `needs_review`

## Where Used

The normalized confidence assessment is used in:

- resume generation
- cover letter generation
- interview prep session provenance
- document review summary provenance
- unified review summary aggregation

## Normalized Fields

Implementations may surface:

- `confidence`
- `confidence_level`
- `requires_human_review`
- `fact_status`
- `evidence_strength`

## Invariants

- Generated drafts remain reviewable and explainable.
- `requires_human_review=true` must be preserved for generated content.
- `gap-risk` questions must remain clearly marked as coaching material, not verified truth.

## UX Guidance

UI should treat `confidence_level` as a trust cue, not as an approval signal.

Recommended rendering:

- `high` -> strong support, but still review before release
- `medium` -> mixed support, review carefully
- `low` -> weak support, show caution
- `needs_review` -> explicit gap-risk or human review required
