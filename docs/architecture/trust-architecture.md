# Trust Architecture

Trust data is modeled as a first-class UX layer.

The review flow should show:

- readiness;
- blockers;
- warnings;
- unsupported claims;
- gap-risk items;
- selected evidence;
- provenance summary;
- recommended actions.

The frontend should treat the backend `review-summary` payload as an anti-corruption layer.
It should not reconstruct trust state from `content_json`, `readiness_json`, or other internal storage fields.

Confidence is deterministic and should be interpreted consistently across documents, interview prep, and review summary.
