# MVP Demo Freeze Candidate

## Purpose

This milestone marks the shift from feature expansion to demo stabilization.

The backend now has enough evidence, document, application, and interview-prep capability for an MVP demo. The next sprint should make the experience coherent, explainable, and calm.

## Freeze Rule

Feature work is frozen unless it directly supports demo readiness.

Allowed work:

- bugs;
- UX clarity;
- stability;
- documentation;
- demo data quality;
- review and provenance visibility;
- smoke checks.

Deferred work:

- new product surfaces;
- new document formats;
- new AI workflows;
- external integrations;
- major data-model expansion;
- speculative scoring or recommendations.

## Demo Quality Goal

The demo should feel like one guided workflow:

```text
profile -> evidence -> vacancy -> documents -> review -> application -> interview prep
```

Not like disconnected feature panels.

## UX Priorities

### 1. Evidence Visibility

Evidence is the core differentiator and must be obvious in the UI.

The user should be able to answer:

- where did this skill come from?
- why was this evidence selected?
- is this fact confirmed?
- what still needs review?
- how is this evidence reused in resume, cover letter, and interview prep?

Acceptance criteria:

- selected skills show source or evidence context when available;
- selected evidence shows fact status and evidence strength;
- unconfirmed evidence is visually distinct from confirmed evidence;
- document review exposes selected evidence without requiring backend knowledge.

### 2. Resume Review UX

Resume review should show what changed between versions.

Minimum useful diff:

- added;
- removed;
- rewritten.

Acceptance criteria:

- reviewer can compare current draft against previous active or previous generated version;
- diff is section-aware when possible;
- unsupported claims remain visible;
- activation stays manual.

### 3. Interview Prep Readability

Interview prep already has strong logic, but it should read as coaching.

Acceptance criteria:

- question cards are less dense;
- suggested answers are grouped and scannable;
- gap-risk questions clearly mark transferable experience or learning plan;
- supporting evidence is visible but not overwhelming;
- readiness warnings guide the next action.

## Stability Priorities

- Streamlit state should not mutate widget keys after widget creation.
- Long flows should survive reruns without losing selected document, vacancy, or interview session.
- Generated documents should render without internal debug copy.
- Empty or partial evidence states should have clear fallbacks.
- Demo seed and manual demo path should both work.

## Documentation Required For Freeze

- `docs/demo_walkthrough_v2.md` stays the canonical walkthrough.
- Milestone docs should describe what is in scope and what is frozen.
- Smoke checklist should cover the full demo path.
- Any known demo caveats should be explicit.

## What Not To Optimize Yet

- PDF/DOCX visual polish.
- Advanced typography.
- More LLM-based personalization.
- Recruiter scoring.
- External job-board submission.

## Exit Criteria

The MVP demo freeze candidate is ready when:

- a user can follow the demo without engineering narration;
- evidence provenance is visible in document and interview workflows;
- resume and cover letter feel role-specific;
- review state and risk are easy to understand;
- application tracking is clearly internal;
- interview prep suggested answers are readable and honest;
- the demo path can be repeated from seed or from a clean manual flow.

