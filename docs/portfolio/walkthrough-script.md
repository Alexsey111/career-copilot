# 5 to 7 Minute Walkthrough Script

This script is deterministic and is meant for a portfolio video, advisor demo, or internal walkthrough.

## Before Recording

- Run `python scripts/reset_demo_environment.py`.
- Start the backend.
- Start Streamlit.
- Log in as the seeded demo user.
- Open the seeded application context once in `Отклики`.

## Timeboxed Script

### 0:00 to 0:30 - Opening

Say:

> Career Copilot helps a candidate turn a resume and a vacancy into trusted application material with explicit human review.

Show:

- the project landing page or main navigation;
- the demo user context;
- the seeded application summary.

### 0:30 to 1:10 - System Health

Show `System Health`.

Call out:

- backend reachable;
- DB reachable;
- seeded demo state;
- counts for vacancies, applications, documents, and interview sessions;
- scenario identifiers.

Say:

> This is a controlled pilot environment, so I can verify the system state before I show any generated output.

### 1:10 to 2:10 - Trust Panel

Open `Trust Panel`.

Show:

- risk level;
- readiness;
- blockers;
- warnings;
- confidence;
- recommended actions;
- selected evidence;
- gap-risk items.

Say:

> The frontend consumes a unified review summary, so it does not need to reconstruct trust state from internal JSON fields.

### 2:10 to 3:30 - Document Review

Open `Document Review Workspace`.

Show:

- a ready document;
- a draft that still requires confirmation;
- provenance summary;
- claims needing confirmation;
- evidence-backed selections.

Say:

> The document is draft-ready, but the UI makes it explicit when something still needs human review.

### 3:30 to 4:50 - Interview Prep

Open `Interview Prep Workspace`.

Show:

- gap-risk questions;
- question provenance;
- readiness summary;
- evidence recommendations;
- low-confidence items if present.

Say:

> Interview prep is coaching material, not verified truth, so the questions remain explainable through vacancy requirements and confirmed evidence.

### 4:50 to 5:50 - Portfolio Closing

Summarize:

- trust is a first-class UX layer;
- provenance is visible;
- actions are deterministic;
- the product stays human-in-the-loop.

If you want to extend the recording to 7 minutes, add:

- a short revisit to `System Health`;
- a quick comparison between the ready document and the trust-risk draft;
- a final glance at the recommended actions.

## What To Show

- Seeded demo state.
- Trust Panel.
- A ready resume.
- A draft with unsupported claims.
- Gap-risk interview prep.
- Deterministic recommended actions.

## What Not To Claim

- Do not claim automatic submission.
- Do not claim the drafts are final truth.
- Do not claim interview prep is a scoring oracle.
- Do not claim provenance is hidden from the user.
