# Production Readiness Audit

## Current status

Career Copilot is still an MVP/pilot-stage product, but the backend now has a safer production baseline.

This document tracks what is already production-ready, what is acceptable for a controlled pilot, and what remains a blocker before public launch.

---

## Completed hardening work

### PR-1 — Config & Runtime Hardening

Status: done

Changes:
- Added runtime safety validation for production.
- Blocked `APP_DEBUG=true` in production.
- Blocked `DEV_AUTH_ENABLED=true` in production.
- Blocked unsafe/default `JWT_SECRET_KEY` in production.
- Blocked default MinIO credentials in production.
- Disabled SQLAlchemy echo by default.
- Cleaned `.env.example`.

Validation:
- `python -m compileall app`
- `pytest -q`
- Production guard check with `APP_ENV=prod APP_DEBUG=true`

---

### PR-2 — Auth & Healthcheck Hardening

Status: done

Changes:
- Hardened password verification against malformed hashes.
- Added proper `WWW-Authenticate: Bearer` response for protected endpoints.
- Restricted `/health/db-info` to `local` and `test`.

Validation:
- Auth tests passed.
- Full test suite passed.
- Manual `/api/v1/auth/me` check returned `401` with Bearer challenge.

---

### PR-3 — Router Cleanup

Status: done

Changes:
- Moved `interviews` router into `build_api_router()`.
- Removed special-case router registration from `main.py`.
- All API routes now go through the canonical API router.

Validation:
- Interview route tests passed.
- Full test suite passed.
- `/api/v1/interviews/sessions` returns authenticated route response.

---

### PR-4 — CORS / Middleware Baseline

Status: done

Changes:
- Added CORS settings.
- Added production guard against wildcard CORS.
- Added CORS middleware.
- Exposed request trace headers.

Validation:
- Full test suite passed.
- Production guard rejects `CORS_ALLOWED_ORIGINS=*`.
- Manual preflight check passed.

---

### PR-5 — Request Logging Baseline

Status: done

Changes:
- Added request completion logging.
- Logged method, path, status code, duration, correlation id.
- Avoided logging request body, query params, authorization headers, emails, filenames, or user content.

Validation:
- Full test suite passed.
- Manual `/health` request produced `http_request_completed` log entry.

---

## Current production-safe areas

### Runtime configuration

Status: controlled baseline

The app now prevents the most dangerous production misconfigurations:
- debug mode in production;
- dev auth in production;
- unsafe JWT secret;
- default object storage credentials;
- wildcard CORS.

### API routing

Status: good

All API routes are now routed through the canonical router.

### Health checks

Status: good for pilot

- `/health`
- `/api/v1/health`

Sensitive DB info is restricted to local/test.

### Auth baseline

Status: acceptable for pilot

Implemented:
- password hashing;
- access tokens;
- refresh tokens;
- refresh token rotation;
- logout;
- logout-all;
- session revocation;
- auth audit events;
- password reset flow.

Needs later:
- real email delivery for password reset;
- stronger rate limits;
- optional 2FA;
- account deletion/export flows.

### Observability baseline

Status: minimal but useful

Implemented:
- correlation id;
- trace headers;
- request completion logs;
- structured logging support.

Needs later:
- Sentry integration;
- metrics endpoint;
- DB query timing;
- AI run cost/latency dashboard;
- alerting.

---

## Acceptable for controlled pilot

These are not ideal, but acceptable for a small controlled pilot:

- Streamlit frontend.
- Local/dev Docker Compose baseline.
- Single backend service.
- PostgreSQL as primary persistence.
- MinIO-compatible storage.
- Manual deployment if documented.
- Deterministic readiness/recommendation logic.
- Human-in-the-loop application submission.

---

## Blockers before public production

### 1. Deployment runbook

Need:
- exact deploy target;
- environment variables;
- migration command;
- rollback procedure;
- backup/restore procedure.

### 2. Storage hardening

Need:
- clear local vs object storage mode;
- bucket creation strategy;
- file size limits;
- allowed file types;
- malware scanning decision;
- object naming strategy.

### 3. Secrets management

Need:
- no real secrets in repo;
- documented secret rotation;
- separate local/staging/prod envs.

### 4. Database operations

Need:
- migration discipline;
- backup strategy;
- restore test;
- connection pool tuning;
- test DB isolation improvement.

### 5. Error monitoring

Need:
- Sentry or equivalent;
- unhandled exception tracking;
- release/environment tags.

### 6. Privacy/data controls

Need:
- user data deletion;
- file deletion;
- log redaction policy;
- data retention policy.

### 7. Password reset productionization

Current reset token is returned by API, which is acceptable only for local/dev.

Need:
- email provider integration;
- no reset token in API response outside local/test;
- reset request rate limiting.

---

## Recommended next PRs

### PR-7 — Password Reset Safety Gate

Prevent reset tokens from being returned in staging/prod.

### PR-8 — File Upload Safety Baseline

Add file size and MIME/extension allowlist.

### PR-9 — Storage Mode Contract

Document and enforce local/minio storage configuration.

### PR-10 — Sentry Baseline

Add optional Sentry init using `SENTRY_DSN`.

### PR-11 — Deployment Runbook

Create minimal deployment checklist and rollback procedure.

---

## Current test baseline

Latest full test suite:

```text
595 passed