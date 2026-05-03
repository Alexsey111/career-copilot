from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401


MIGRATION_TEST_DATABASE_URL = os.getenv(
    "MIGRATION_TEST_DATABASE_URL",
    "postgresql+psycopg://career_user:career_pass@localhost:5432/career_copilot_migration_test",
)


def _ensure_test_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    db_name = url.database
    admin_url = url.set(database="postgres")

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        engine.dispose()


def _reset_public_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def test_alembic_head_matches_orm_metadata(monkeypatch: pytest.MonkeyPatch):
    _ensure_test_database_exists(MIGRATION_TEST_DATABASE_URL)

    monkeypatch.setenv("DATABASE_URL", MIGRATION_TEST_DATABASE_URL)
    monkeypatch.setenv("SYNC_DATABASE_URL", MIGRATION_TEST_DATABASE_URL)
    get_settings.cache_clear()

    engine = create_engine(MIGRATION_TEST_DATABASE_URL, future=True)

    try:
        _reset_public_schema(engine)

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)

        missing: list[str] = []

        for table in Base.metadata.sorted_tables:
            db_columns = {column["name"] for column in inspector.get_columns(table.name)}
            orm_columns = set(table.columns.keys())

            for column_name in sorted(orm_columns - db_columns):
                missing.append(f"{table.name}.{column_name}")

        assert not missing, "Alembic schema is missing ORM columns: " + ", ".join(missing)

    finally:
        _reset_public_schema(engine)
        engine.dispose()