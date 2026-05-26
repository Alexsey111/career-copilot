# Review and Application Ops

## What was done

- Consolidated document review UX into `frontend/streamlit/components/document_review_workspace.py`.
- Made `render_document_approval_step` in `frontend/streamlit/flows/document_application_flow.py` a thin wrapper over the workspace.
- Preserved `approved_resume` and `approved_cover_letter` session state updates after approval.
- Added structured document diff and review summary flows for pre-approve review.
- Kept application tracking and interview preparation as explicit human-in-the-loop steps.

## Added endpoints

- `GET /api/v1/documents/{document_id}/history`
- `GET /api/v1/documents/{document_id}/diff/{other_document_id}`
- `GET /api/v1/documents/{document_id}/review-summary`
- `PATCH /api/v1/documents/{document_id}/review`
- `POST /api/v1/documents/{document_id}/activate`
- `POST /api/v1/documents/{document_id}/rollback`
- `GET /api/v1/applications`
- `GET /api/v1/applications/analytics/summary`
- `GET /api/v1/applications/{application_id}/timeline`
- `GET /api/v1/applications/{application_id}/activity-log`
- `GET /api/v1/applications/{application_id}/workflow`
- `PATCH /api/v1/applications/{application_id}/status`

## Product boundaries

- Document review is a manual approval workflow, not an automatic publish step.
- Approval changes local document state only; it does not send anything externally.
- Application tracking is an internal CRM-like layer for the project, not an auto-apply engine.
- Manual submission is still explicit and user-triggered.
- Interview preparation is advisory and internal; it does not contact employers.

## Covered by tests

- `tests/test_resume_enhance_flow.py`
- `tests/test_document_activate.py`
- `tests/test_document_diff.py`
- `tests/test_mvp_flow_e2e.py`

## What is not automated

- Auto-approval of documents.
- Auto-export to external platforms.
- Auto-submit of applications.
- Auto follow-up or reminder sending.
- Employer-facing interview communication.

## Next candidates

- Approval audit trail UI.
- Reminder dismissal and snooze actions.
- Export history visibility in the workspace.
- Better document branch visualization.
- Application state transition shortcuts with stronger validation.
- Smarter review-summary wording for non-technical reviewers.
