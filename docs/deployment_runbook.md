# Deployment Runbook

This runbook is intentionally minimal. It covers the local pilot setup only and avoids cloud-specific deployment shape.

## Supported Runtime

The local pilot baseline is:

- Docker Compose
- FastAPI backend
- PostgreSQL
- Redis
- MinIO-compatible object storage

## Required Environment Variables

Use [.env.example](../.env.example) as the baseline. For local pilot runs, the most important values are:

- `APP_ENV`
- `DATABASE_URL`
- `SYNC_DATABASE_URL`
- `JWT_SECRET_KEY`
- `STORAGE_MODE`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET`
- `CORS_ALLOWED_ORIGINS`
- `DEV_AUTH_ENABLED`

## One-Command Local Start

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Start the full local stack and verify it:

```bash
make local-start
```

`make local-start` will:

- start `postgres`, `redis`, `minio`, and `api` via Docker Compose;
- wait for the database to be reachable;
- apply migrations;
- verify `GET /health`;
- verify `GET /api/v1/health/db-info`.

3. If you want the controlled demo state, seed it after startup:

```bash
python scripts/reset_demo_environment.py
```

## Health Verification

You can re-run the local health checks at any time:

```bash
make local-health
```

This checks:

- database connectivity;
- backend `/health`;
- backend `/api/v1/health/db-info`.

## Demo and Pilot References

- [Architecture index](./architecture/index.md)
- [Demo walkthrough](./demo_walkthrough.md)
- [Pilot readiness checklist](./pilot_readiness_checklist.md)
- `python scripts/reset_demo_environment.py`
- `make local-start`
- `make local-health`
