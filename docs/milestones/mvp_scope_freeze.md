# MVP Scope Freeze

## Purpose

This note freezes the MVP scope for stabilization, polish, and demo readiness.

The product story is now:

```text
resume upload
-> GitHub import
-> evidence confirmation
-> vacancy matching
-> tailored documents
-> application tracking
-> interview prep
-> suggested answers
```

## In Scope For MVP

- Resume intake and profile extraction.
- GitHub public import.
- Evidence bank and evidence review.
- Vacancy import and vacancy analysis.
- Tailored resume generation.
- Tailored cover letter generation.
- Document review workspace.
- Internal application tracking.
- Interview prep workspace.
- Suggested answer display.
- Provenance, confidence, warnings, and human review boundaries.

## Out Of Scope For MVP

- External job-board application submission.
- Paid ATS integrations.
- PDF/DOCX visual template engine.
- Autonomous claim creation.
- Hiring probability prediction.
- Live employer communication.
- Fully automated career planning.

## Stabilization Priorities

1. Keep deterministic generation stable.
2. Keep evidence provenance visible.
3. Keep unsupported claims honest.
4. Keep Streamlit state predictable.
5. Keep demo path reproducible from a seeded or manually prepared workspace.

## Demo Readiness Bar

The demo is ready when a user can complete the core workflow without explaining backend internals:

- uploaded resume is visible;
- imported GitHub evidence is visible;
- evidence can be reviewed;
- vacancy context is clear;
- tailored resume and cover letter are understandable;
- review state is visible;
- application tracker reflects the target vacancy;
- interview prep includes suggested answers and risk notes.

