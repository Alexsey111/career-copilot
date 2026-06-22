from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_APP_PATH = ROOT_DIR / "frontend" / "streamlit" / "app.py"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Streamlit frontend on an available local port."
    )
    parser.add_argument(
        "--app",
        default=str(DEFAULT_APP_PATH),
        help="Path to the Streamlit app entry point.",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host interface to bind Streamlit to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Explicit port to use. If omitted, a free local port is selected.",
    )
    return parser.parse_args()


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _resolve_port(explicit_port: int | None) -> int:
    if explicit_port is not None:
        return explicit_port

    env_port = os.getenv("STREAMLIT_PORT")
    if env_port:
        return int(env_port)

    return _pick_free_port()


def main() -> int:
    args = _parse_args()
    port = _resolve_port(args.port)
    app_path = Path(args.app).resolve()

    if not app_path.exists():
        raise FileNotFoundError(f"Streamlit app not found: {app_path}")

    print(f"Starting Streamlit on http://{args.host}:{port}")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        args.host,
        "--server.port",
        str(port),
    ]
    try:
        return subprocess.run(command, cwd=ROOT_DIR).returncode
    except KeyboardInterrupt:
        print("Stopping Streamlit...")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
