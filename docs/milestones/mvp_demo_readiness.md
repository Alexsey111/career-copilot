# MVP Demo Readiness

## Demo seed available

- `scripts/seed_demo.py` creates a reproducible demo user and seeded workspace state.
- The seed includes source resume state, confirmed achievements, evidence snippets, a vacancy set, vacancy analysis, draft documents, an internal application tracker record, and an interview prep session.
- The seeded application is an internal tracker record.
- No external application is submitted.

## Walkthrough available

- `docs/demo_walkthrough.md` documents the operator path for running the demo.
- The walkthrough covers backend startup, migrations, seeding, Streamlit login, review, application tracking, interview prep, and career strategy views.

## Core flows covered

- Evidence Workspace.
- Document Review Workspace.
- Applications dashboard.
- Interview Prep Workspace.
- Career Strategy workspace.
- Vacancy Intelligence in vacancy and application views.

## Human-in-the-loop boundaries

- Resume and cover letter generation stay reviewable before activation.
- Document approval remains a manual action.
- Application tracking is internal unless the user explicitly marks the record as submitted through the workflow.
- Interview prep remains advisory and does not contact employers.
- Career strategy output is deterministic operational guidance, not autonomous planning.

## Known limitations

- Demo seeding assumes the database schema is already migrated to head.
- The demo relies on local deterministic data, not a live external job board sync.
- Test teardown can deadlock if multiple DB-heavy pytest runs overlap in parallel.
- Some review and activation paths still depend on the current schema state being clean before seeding.

## Pre-demo commands

```powershell
alembic upgrade head
python -m scripts.seed_demo
python -m pytest tests/test_mvp_flow_e2e.py -q
python -m pytest tests/test_document_activate.py tests/test_evidence_api.py -q
python -m compileall -q scripts app frontend tests
```

## What not to claim in demo

- Do not claim the application was automatically submitted externally.
- Do not claim hiring probability or recruiter prediction.
- Do not claim autonomous career planning.
- Do not claim hidden AI scoring or invisible ranking.
- Do not claim the demo is a live job-board integration.
