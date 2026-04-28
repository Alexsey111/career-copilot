# scripts\dev_db_reset.py

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402


TABLES: list[str] = [
    "application_records",
    "interview_sessions",
    "document_versions",
    "vacancy_analyses",
    "vacancies",
    "candidate_achievements",
    "candidate_experiences",
    "candidate_profiles",
    "file_extractions",
    "source_files",
    "ai_runs",
    "users",
]

SAFE_ENV_VALUES = {"local", "dev", "development", "test"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset local/dev career-copilot database data.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive reset without interactive prompt.",
    )
    return parser.parse_args()


def normalize_dsn(sync_database_url: str) -> str:
    return sync_database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def validate_safe_environment(*, app_env: str, dsn: str) -> None:
    normalized_env = app_env.strip().lower()

    if normalized_env not in SAFE_ENV_VALUES:
        raise RuntimeError(
            f"Refusing to reset database because APP_ENV={app_env!r}. "
            f"Allowed values: {sorted(SAFE_ENV_VALUES)}"
        )

    if "localhost" not in dsn and "127.0.0.1" not in dsn:
        raise RuntimeError(
            "Refusing to reset database because DSN does not look local. "
            f"DSN: {dsn}"
        )

    if "career_copilot" not in dsn:
        raise RuntimeError(
            "Refusing to reset database because DSN does not contain expected "
            f"database name marker 'career_copilot'. DSN: {dsn}"
        )


def print_counts(cur) -> None:
    for table in TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"{table:<28} {count}")


def main() -> None:
    args = parse_args()
    settings = get_settings()
    dsn = normalize_dsn(settings.sync_database_url)

    validate_safe_environment(app_env=settings.app_env, dsn=dsn)

    print("DEV DB RESET")
    print(f"APP_ENV:  {settings.app_env}")
    print(f"Database: {dsn}")
    print("-" * 72)

    if not args.yes:
        print("This will delete local/dev demo data from these tables:")
        for table in TABLES:
            print(f"- {table}")

        confirmation = input("Type RESET to continue: ").strip()
        if confirmation != "RESET":
            print("Reset cancelled.")
            return

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            print("Counts before reset:")
            print_counts(cur)
            print("-" * 72)

            table_list = ", ".join(TABLES)
            print(f"Executing: TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;")
            cur.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;")

            print("-" * 72)
            print("Counts after reset:")
            print_counts(cur)

    print("-" * 72)
    print("Database reset complete.")
    print("Reminder: MinIO bucket cleanup is separate and still required.")
    print("-" * 72)


if __name__ == "__main__":
    main()