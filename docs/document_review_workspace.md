# Document Review Workspace

`frontend/streamlit/components/document_review_workspace.py` is now the source of truth for the document review UX.

## What lives here

- Review workspace layout
- Readiness panel
- Structured AI diff panel
- Claims requiring confirmation
- Selected achievements with rationale
- Keywords coverage
- Final rendered preview
- Action bar for approve, export, enhance, and back

## Why this exists

- The older review UI in `frontend/streamlit/app.py` was fragmented across preview, summary, diff, readiness, and approve blocks.
- The workspace consolidates those pieces into one review surface.
- This makes the approval flow easier to trust and easier to maintain.

## Integration points

- Step 9 in `frontend/streamlit/app.py` is now a thin wrapper over the workspace.
- The dedicated `Document Review Workspace` tab uses the same component layer.
- Both paths update `approved_resume` and `approved_cover_letter` in Streamlit session state after approval.

## Evidence used

The workspace now shows evidence provenance for generated documents:

- `selected_evidence_ids`
- `evidence_selection_reason`
- snippet `fact_status` and `evidence_strength` when available from `/evidence/snippets/{id}`

This connects document approval to reusable evidence provenance.

## Notes

- The workspace uses the structured document diff source, not `rendered_text` diff.
- The backend still owns document generation, review summary, readiness, and diff data.
- Streamlit owns aggregation and review UX composition.
