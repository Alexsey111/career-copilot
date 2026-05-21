from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.demo_scenarios import get_demo_scenarios


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    print("Resetting demo environment...")
    _run([sys.executable, str(PROJECT_ROOT / "scripts" / "dev_db_reset.py"), "--yes"])
    _run([sys.executable, str(PROJECT_ROOT / "scripts" / "seed_demo.py")])
    _run([sys.executable, str(PROJECT_ROOT / "scripts" / "check_demo_trust_states.py")])

    print()
    print("Demo scenarios:")
    for scenario in get_demo_scenarios():
        print(f"- {scenario['code']}: {scenario['label']}")

    print()
    print("Next steps:")
    print("1. Start the backend if it is not already running.")
    print("2. Start Streamlit and open the System Health tab.")
    print("3. Use the Trust Panel to compare readiness, confidence, and actions.")


if __name__ == "__main__":
    main()
