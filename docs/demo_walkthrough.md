# Demo Walkthrough

## Purpose

This walkthrough seeds a reproducible demo scene for operator use.

## Steps

1. Start the backend.
2. Apply migrations.
3. Run `python scripts/reset_demo_environment.py` or `python -m scripts.seed_demo`.
4. Start Streamlit.
5. Log in as the demo user printed by the seed script.
6. Open `System Health`.
7. Confirm backend reachability, DB reachability, seeded state, and the scenario identifiers.
8. Open `Evidence Workspace`.
9. Open `Document Review Workspace`.
10. Open `Отклики` and select the seeded application once so the vacancy context is available.
11. Open `Trust Panel`.
12. Show the ready resume state.
13. Show the cover letter state with claims requiring confirmation.
14. Open `Interview Prep Workspace`.
15. Show the interview prep state with gap-risk items and readiness warnings.
16. Review the seeded documents again if you want to compare the trust summary with the raw document view.
17. Open `Career Strategy`.

## What To Show

- Ready resume and evidence-backed content.
- A document draft that still requires human review.
- Unified `review-summary` in Trust Panel.
- Interview prep gap-risk items and recommended actions.
- Correlation between trust state and UX controls.
- Scenario identifiers for repeatable demo narration.

## What Not To Claim

- Do not claim automatic submission.
- Do not claim generated content is verified truth.
- Do not claim low-confidence or gap-risk content is final.
- Do not claim the demo flow removes human review.

## Demo Notes

- Demo application is an internal tracker record.
- No external application is submitted.
- The walkthrough stays human-in-the-loop; nothing is auto-submitted outside the app.
- The Trust Panel is the operator view for risk, confidence, evidence, and recommended actions.
- Scenario A - Ready application
- Scenario B - Unsupported claims
- Scenario C - Interview gap-risk
- Scenario D - Low confidence evidence

## Demo Checks

Run these after seeding to verify the controlled pilot scene:

```bash
python -m scripts.seed_demo
python scripts/check_demo_trust_states.py
```
