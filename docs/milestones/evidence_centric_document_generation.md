# Evidence-Centric Document Generation

## Milestone

Document generation now treats evidence as the primary input, not as decoration after text is drafted.

The resume and cover letter pipeline uses candidate profile data, vacancy analysis, confirmed achievements, and evidence snippets to build reviewable documents with provenance.

## What Is In Scope

- Tailored resume content from matched vacancy requirements.
- Deterministic skill normalization and noisy profile cleanup.
- Evidence-backed selected achievements.
- Structured project sections with role, project name, and bullets.
- Competency mapping with relevance guards.
- Cover letter composition from matched requirements and confirmed project value.
- Review warnings for weak, missing, or unconfirmed evidence.

## Current Quality Bar

- Generated documents should explain why the candidate fits the role.
- Project bullets should describe the problem solved, not only the technology used.
- Competency mapping must prefer specific evidence over generic workflow evidence.
- Missing evidence should be stated honestly instead of overclaimed.

## Non-Goals

- No automatic external application submission.
- No hidden recruiter score or hiring probability claim.
- No autonomous invention of candidate facts.
- No visual PDF/DOCX template engine in this milestone.

## Demo Signal

The demo should show that a generated resume or cover letter can be traced back to selected evidence, confirmed achievements, and vacancy requirements.

