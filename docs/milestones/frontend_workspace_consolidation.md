# Frontend Workspace Consolidation

## Legacy interview UI retired

- Removed the old interview dashboard and mock interview flow from inline `frontend/streamlit/app.py` composition.
- Retired legacy interview session state keys that were only supporting the old flow.
- Kept backend interview endpoints untouched.

## Canonical prep workspace

- `frontend/streamlit/components/interview_prep_workspace.py` is the only interview prep surface now.
- The MVP flow now points users to the prep workspace instead of duplicating interview logic inline.
- Prep session creation, question generation, evidence linking, and readiness live in one component layer.

## Canonical applications dashboard

- `render_application_dashboard` is the single applications tracking surface.
- The step-based dashboard was removed from the linear MVP flow.
- The dedicated `Отклики` tab now owns analytics, reminders, workflow transitions, timeline, and activity log.

## Review workspace consolidation

- `render_document_approval_step` is a thin wrapper over `render_document_review_workspace_tab`.
- Document review is handled by the workspace component instead of a separate legacy step UI.
- The same workspace logic is reused in both the MVP flow and the dedicated tab.

## Session state cleanup

- Removed legacy `interview_session` and `interview_answers_result` session keys.
- Removed redundant `application_list` session state after consolidating applications tracking.
- Kept only the state that is still needed by the current workspace layers.

## Removed duplicate workflow surfaces

- Interview tracking no longer has parallel legacy and workspace paths.
- Application tracking no longer has both a step dashboard and a dedicated dashboard with overlapping behavior.
- The frontend now exposes one canonical surface per major workflow.

## Current frontend layering

- `frontend/streamlit/app.py` now acts as the entrypoint and tab composer.
- `frontend/streamlit/flows/mvp_flow.py` owns the linear MVP orchestration.
- `frontend/streamlit/pages/*.py` own the individual page surfaces.
- `frontend/streamlit/components/document_review_workspace.py` owns document review UX.
- `frontend/streamlit/components/interview_prep_workspace.py` owns interview prep UX.
- `render_application_dashboard` owns applications tracking and operational workflow views.
