# Demo Walkthrough V2

## Purpose

This walkthrough is the primary demo script for the evidence-driven MVP.

The goal is to show a deterministic career workflow:

```text
candidate data -> evidence -> tailored documents -> application tracking -> interview prep
```

## Setup

1. Start the backend.
2. Apply migrations.
3. Start Streamlit.
4. Use either a seeded demo user or a clean user prepared for the walkthrough.

Optional deterministic seed:

```powershell
python -m scripts.seed_demo
```

## Script

### 1. Upload Resume

- Open the resume intake step.
- Upload or select the candidate resume.
- Show extracted profile fields, skills, achievements, and experience.
- Explain that extracted facts are not automatically treated as perfect truth.

### 2. GitHub Import

- Open GitHub import.
- Import the candidate public repository.
- Show repository evidence such as backend architecture, stack, workflow, tests, or infrastructure.
- Explain that repository data becomes evidence, not marketing copy.

### 3. Evidence Confirmation

- Open Evidence Workspace.
- Review evidence snippets.
- Highlight fact status, evidence strength, source, and reusable evidence.
- Confirm that weak or unconfirmed evidence remains visibly different from confirmed evidence.

### 4. Vacancy Import

- Add or select a target vacancy.
- Run vacancy analysis.
- Show matched requirements and gaps.
- Explain that missing requirements are not silently claimed.

### 5. Tailored Resume

- Generate the tailored resume.
- Open Document Review Workspace.
- Show:
  - vacancy-aligned summary;
  - normalized skills;
  - structured project sections;
  - project bullets grounded in evidence;
  - competency map relevance guards.
- Point out that Git and generic AI are not overclaimed without direct evidence.

### 6. Tailored Cover Letter

- Generate the tailored cover letter.
- Show the two-part composition:
  - why the role is relevant;
  - what concrete project value the candidate can bring.
- Confirm that the letter avoids raw buzzword lists such as `LLM, ChatGPT, Automation`.

### 7. Review

- Use Document Review Workspace.
- Show warnings, confidence, selected evidence, and review controls.
- Explain that the user must review and activate documents before using them.

### 8. Application Tracking

- Open the application tracker.
- Create or select an application tied to the vacancy.
- Move it through internal states such as draft, ready, applied, screening, interview, offer, rejected, or withdrawn.
- State clearly that this is internal tracking, not external submission.

### 9. Interview Prep

- Open Interview Prep Workspace.
- Create or select an interview prep session.
- Show generated questions, readiness state, evidence links, and gap-risk warnings.

### 10. Suggested Answers

- Open a question card.
- Show the suggested answer sections:
  - Situation
  - Task
  - Action
  - Result
  - Tech stack
  - Tradeoffs
  - Talking points
- Read the UX warning:
  - `Черновик ответа. Проверьте и адаптируйте под свой реальный опыт.`
- For a gap-risk question, show that the answer uses learning or transferable experience rather than overclaiming.

## What To Emphasize

- The product is evidence-driven and reviewable.
- Generation is deterministic where possible.
- Weak evidence stays visible.
- Documents and interview prep reuse the same evidence graph.
- The user remains in control before anything is sent outside the app.

## What Not To Claim

- Do not claim automatic job submission.
- Do not claim generated text is verified truth.
- Do not claim hiring probability prediction.
- Do not claim private repository access unless explicitly configured.
- Do not claim interview answers should be used without personal review.

## Demo Success Criteria

- Resume upload works.
- GitHub import produces evidence.
- Evidence review is visible.
- Vacancy analysis produces matches and gaps.
- Tailored resume is evidence-backed.
- Tailored cover letter is role-specific and avoids buzzword dumping.
- Review controls and warnings are visible.
- Application tracking works as an internal workflow.
- Interview prep shows questions, readiness, supporting evidence, and suggested answers.

