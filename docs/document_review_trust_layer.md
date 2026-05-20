# Document Review Trust Layer

## Purpose
This layer makes document approval explicit and safe.
It separates visibility, validation, and final approval.

## Components
- `review-summary` shows the document state before approval.
- `readiness gate` evaluates whether the document is safe to approve.
- `approve blocker contract` prevents approval when readiness is false.
- `application submit gate` remains a second line of defense.

## Review Summary
`GET /documents/{document_id}/review-summary` is the operator-facing preview.
It surfaces:
- `claims_needing_confirmation`
- `warnings`
- `selected_achievements`
- `matched_keywords`
- `missing_keywords`
- `selection_rationale`
- `readiness`

The summary is informational.
It does not approve the document by itself.

## Readiness Gate
Readiness is computed with the existing `ReadinessGateService`.
It checks whether the document is safe to move forward.

### Blockers
The current blocker set includes:
- unresolved claims needing confirmation
- unresolved critical evaluation failures
- missing approval state for review
- inactive document state

### Warnings
Warnings are advisory and do not automatically block approval by themselves.
They include:
- coverage gaps
- low ATS score
- achievements with missing metrics

## Approve Blocker Contract
`PATCH /documents/{document_id}/review` with `review_status=approved`
must fail with `409` when `readiness.ready == false`.

Expected blocked response:
- a clear message that approval is blocked
- readiness details
- blockers list
- warnings list
- readiness score when available

## Why Submit Gate Stays Second
Approval and submit solve different problems.

- Approval confirms that a human reviewed the document content.
- Submit confirms that an application can be marked as sent.

Keeping both gates is intentional:
- review blocks unsafe document approval
- submit blocks unsafe application state transitions

This reduces the chance of a bad document being both approved and submitted.

## AI Boundary
AI can help draft and analyze content.
AI cannot:
- confirm claims on its own
- bypass readiness blockers
- auto-approve documents
- replace human review

Claims still require explicit human confirmation.

## Happy Path
1. Generate the document.
2. Open `review-summary`.
3. Verify claims, warnings, keywords, and achievements.
4. Readiness is `true`.
5. Approve the document.
6. Activate it if needed.
7. Use it in application flow.

## Blocked Path
1. Generate the document.
2. Open `review-summary`.
3. See unresolved claims or other blockers.
4. Attempt approval.
5. API returns `409 Conflict`.
6. Fix the document or claims first.
7. Re-check readiness and retry approval.

## Product Boundary
This is a trust layer, not an automation layer.

- no silent approval
- no AI self-signoff
- no submit without explicit human action
- no auto-repair of blockers

## Related Docs
- [Application Operations](./application_operations.md)
- [document_mutation_service](./document_mutation_service.md)
- [readiness_evaluation_service](./readiness_evaluation_service.md)
