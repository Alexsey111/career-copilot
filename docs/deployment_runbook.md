# Deployment Runbook

## Supported Runtime

Current deployment baseline:
- FastAPI backend
- PostgreSQL
- Redis
- MinIO-compatible object storage
- Docker Compose
- Uvicorn

Current deployment target:
- single-node pilot deployment

## Required Environment Variables

Only operationally critical variables are listed here.

### Core Runtime
- `APP_ENV`
- `DATABASE_URL`
- `SYNC_DATABASE_URL`
- `JWT_SECRET_KEY`

### Storage
- `STORAGE_MODE`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET`

### Auth / Security
- `CORS_ALLOWED_ORIGINS`
- `DEV_AUTH_ENABLED`

### Monitoring
- `SENTRY_DSN`

## First Deploy Procedure

1. Clone the repository.
2. Create a `.env` file.
3. Start infrastructure:

```bash
docker compose up -d postgres redis minio
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

6. Verify the health endpoint:

```bash
curl http://localhost:8000/health
```

## Upgrade Procedure

1. Pull the latest code.
2. Review migration files.
3. Backup the database.
4. Run migrations:

```bash
alembic upgrade head
```

5. Restart the API service.
6. Verify the health endpoint.
7. Verify the login flow.
8. Verify the upload flow.

## Rollback Procedure

1. Stop the API service.
2. Restore the previous release.
3. Roll back the database only if the migration is reversible.
4. Restart the API service.
5. Verify the health endpoint.

## Migration Warning

Do not run destructive migrations without:
- DB backup;
- rollback plan;
- validation on staging or a local snapshot.

## Pilot Operational Checklist

Before pilot usage:
- production JWT secret configured;
- `DEV_AUTH_ENABLED=false`;
- `SENTRY_DSN` configured;
- backups enabled;
- MinIO bucket reachable;
- health endpoint reachable;
- upload flow verified;
- auth flow verified;
- CORS configured for the frontend domain.

## Demo and pilot references

- [Architecture index](./architecture/index.md)
- [Demo walkthrough](./demo_walkthrough.md)
- [Pilot readiness checklist](./pilot_readiness_checklist.md)
- `python scripts/reset_demo_environment.py`
- `make demo`
