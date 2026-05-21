# Document Provenance Contract

## Purpose

Document provenance explains why a generated resume or cover letter contains specific claims, evidence, achievements, and vacancy-matching content.

## Location

Stored in:

- `DocumentVersion.content_json["provenance"]`
- `DocumentVersion.content_json["meta"]["provenance"]` for compatibility
- exposed through `GET /api/v1/documents/{document_id}/review-summary`

## Fields

- `source`
- `generation_mode`
- `analysis_id`
- `based_on_achievements`
- `selected_achievement_ids`
- `selected_evidence_ids`
- `evidence_selection_reason`
- `confidence`
- `generation_prompt_version`
- `generated_at`
- `requires_human_review`

## Product invariant

Generated documents are not final user-facing truth until reviewed.

`requires_human_review=true` must be preserved for generated drafts.

## UX guidance

Review UI should show:

- selected evidence ids / selected evidence snippets
- selected achievements
- confidence
- warnings
- claims needing confirmation
- missing vacancy keywords

## Backward compatibility

Older documents may only have provenance-like data in `meta`.

Readers should use:

1. `content_json["provenance"]`
2. fallback to `content_json["meta"]["provenance"]`
3. fallback to legacy meta fields
