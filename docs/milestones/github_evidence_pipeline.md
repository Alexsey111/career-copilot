# GitHub Evidence Pipeline

## Milestone

GitHub import is now part of the evidence pipeline rather than a standalone repository parser.

Repository signals can enrich candidate evidence with architecture, backend, automation, infrastructure, testing, and workflow context.

## What Is In Scope

- Public repository import.
- Repository evidence extraction.
- Architecture and stack signals.
- Repository evidence snippets available for downstream document generation.
- Evidence diversity balancing so backend, automation, computer vision, analytics, and AI workflow signals do not collapse into one narrative.
- Specific evidence matching for competencies such as Git, FastAPI, Docker, PostgreSQL, and testing.

## Current Quality Bar

- Repository evidence should support concrete claims.
- Git evidence must come from repository or version-control signals.
- Backend claims should be grounded in backend or API evidence.
- Infrastructure claims should be grounded in Docker, Redis, PostgreSQL, or deployment-related evidence.
- Generic workflow evidence should not be reused for unrelated competencies.

## Non-Goals

- No private repository crawling without explicit user authorization.
- No claim that repository import proves production impact.
- No automatic rewriting of user profile facts from GitHub alone.

## Demo Signal

The demo should show GitHub import creating reusable evidence that later appears in resume projects, competency mapping, and interview prep.

