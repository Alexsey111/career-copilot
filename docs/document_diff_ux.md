# Document Diff UX

This page explains how the pre-approve document diff works in the MVP.

## Diff source

- The diff is section-aware and uses `content_json["sections"]` from both documents.
- It does not compare `rendered_text`.
- The current implementation focuses on stable, review-friendly structure instead of raw prose.

## Covered sections

The first MVP pass compares these sections:

- `skills`
- `matched_keywords`
- `summary_bullets`
- `selected_achievements`
- `claims_needing_confirmation`
- `warnings`

## Why not rendered text diff

- `rendered_text` is fragile because formatting, ordering, and punctuation can change without meaningfully changing the document.
- A text diff is noisy for humans and hard to trust during approval.
- Section-level comparison makes the changes easier to explain and easier to review.

## How Streamlit finds the base document

- The approval UI first checks the target document history.
- If the history contains `derived_from_id`, Streamlit uses that as the base document.
- If lineage is not available, Streamlit falls back to the active document in the same scope:
  - same `document_kind`
  - same `vacancy_id`
- This keeps the UI resilient when lineage data is incomplete.

## How the diff supports human review

- The UI shows a short summary of what AI added, removed, or changed before approve.
- Reviewers can quickly spot:
  - added keywords
  - removed keywords
  - changed achievements
  - new claims that need confirmation
  - new warnings
- The diff is meant to help the user decide whether the draft is safe to approve.

## Limitation

- This is not a semantic diff yet.
- It does not understand meaning, paraphrases, or context beyond the structured sections.
- Future versions can add semantic comparison on top of this stable structured baseline.
