from __future__ import annotations

import sys
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402


TABLES: list[str] = [
    "users",
    "source_files",
    "file_extractions",
    "candidate_profiles",
    "candidate_experiences",
    "candidate_achievements",
    "vacancies",
    "vacancy_analyses",
    "document_versions",
    "application_records",
    "interview_sessions",
    "ai_runs",
]


def main() -> None:
    settings = get_settings()
    dsn = settings.sync_database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    print("DEV DB COUNTS")
    print(f"Database: {dsn}")
    print("-" * 72)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for table in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"{table:<28} {count}")

    print("-" * 72)
    print("Done.")


if __name__ == "__main__":
    main()