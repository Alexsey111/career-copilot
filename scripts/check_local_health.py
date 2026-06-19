from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
DEFAULT_BASE_URL = "http://localhost:7000"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify local runtime health.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for the backend health checks.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="How long to wait for database and HTTP readiness.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval while waiting for readiness.",
    )
    return parser.parse_args()


def _render_postgres_dsn(database_url: str) -> str:
    url = make_url(database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _wait_for_database(*, timeout_seconds: int, interval_seconds: float) -> None:
    settings = get_settings()
    dsn = _render_postgres_dsn(settings.database_url)
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            print("Database is reachable.")
            return
        except Exception as exc:  # pragma: no cover - connection errors vary by environment
            last_error = exc
            time.sleep(interval_seconds)

    raise RuntimeError("Database did not become ready in time.") from last_error


def _run_migrations() -> None:
    print("Running migrations...")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT_DIR,
        check=True,
    )


def _fetch_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def _wait_for_http(
    *,
    base_url: str,
    path: str,
    timeout_seconds: int,
    interval_seconds: float,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    url = f"{base_url.rstrip('/')}{path}"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            payload = _fetch_json(url)
            print(f"Verified {path}: {payload}")
            return payload
        except (HTTPError, URLError, TimeoutError, socket.timeout, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(interval_seconds)

    raise RuntimeError(f"HTTP check for {path} did not become ready in time.") from last_error


def main() -> int:
    args = _parse_args()
    settings = get_settings()

    print("Checking database connectivity...")
    _wait_for_database(
        timeout_seconds=args.timeout_seconds,
        interval_seconds=args.interval_seconds,
    )
    _run_migrations()

    print("Checking backend health...")
    health_payload = _wait_for_http(
        base_url=args.base_url,
        path="/health",
        timeout_seconds=args.timeout_seconds,
        interval_seconds=args.interval_seconds,
    )
    if health_payload.get("status") != "ok":
        raise RuntimeError("Backend health endpoint did not return ok.")

    print("Checking backend diagnostics...")
    diagnostics_payload = _wait_for_http(
        base_url=args.base_url,
        path=f"{settings.api_prefix}/health/db-info",
        timeout_seconds=args.timeout_seconds,
        interval_seconds=args.interval_seconds,
    )
    environment = diagnostics_payload.get("environment")
    if environment not in {"local", "test"}:
        raise RuntimeError("Diagnostics endpoint returned an unexpected environment.")

    print("Local health checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
