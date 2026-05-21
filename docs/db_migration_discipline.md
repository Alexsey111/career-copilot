# Migration Principles

Database migrations must:
- be deterministic;
- be reviewable;
- avoid silent data loss;
- support rollback where possible;
- be tested locally before deployment.

## Naming Rules

Migration names should describe intent.

Good:
- `add_auth_events_table`
- `add_pipeline_execution_indexes`
- `add_document_review_status`

Bad:
- `update_models`
- `fix_stuff`
- `migration_12`

## Required Workflow

1. Update SQLAlchemy models.
2. Generate migration:

```bash
alembic revision --autogenerate -m "message"
```

3. Review the generated migration manually.
4. Verify downgrade exists when possible.
5. Apply locally:

```bash
alembic upgrade head
```

6. Run tests.
7. Validate critical flows manually.

## Destructive Migration Policy

Avoid destructive migrations by default.

Dangerous operations:
- `DROP COLUMN`
- `DROP TABLE`
- irreversible type conversion
- mass `UPDATE` without backup
- deleting historical data

Before a destructive migration:
- create a DB backup;
- document a rollback plan;
- verify on staging or a local snapshot.

## Rollback Expectations

Migrations should support downgrade whenever practical.

If downgrade is impossible:
- explicitly document why;
- document the recovery procedure.

## Large Table Guidance

For large tables:
- avoid long-running locks;
- prefer additive changes;
- backfill separately;
- create indexes carefully.

## Pilot Release Checklist

Before release:
- migrations reviewed;
- downgrade reviewed;
- backup verified;
- `alembic upgrade` tested;
- smoke tests passed;
- auth flow checked;
- upload flow checked;
- core pipeline checked.
