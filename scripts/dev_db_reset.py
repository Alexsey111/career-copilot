from __future__ import annotations

import sys
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    dsn = settings.sync_database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    print("DEV DB RESET")
    print(f"Database: {dsn}")
    print("-" * 72)
    print("Executing: TRUNCATE TABLE users CASCADE;")

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE users CASCADE;")

    print("Database reset complete.")
    print("Reminder: MinIO bucket cleanup is separate and still required.")
    print("-" * 72)


if __name__ == "__main__":
    main()