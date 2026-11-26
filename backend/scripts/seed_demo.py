"""Seed a labeled demo scenario into the configured local SQLite database.

Run from the repository root:
    python backend/scripts/seed_demo.py cyclone
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import init_database
from app.demo_service import run_demo_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ResQ Command with synthetic demo data.")
    parser.add_argument(
        "scenario",
        choices=("cyclone", "flood", "earthquake"),
        nargs="?",
        default="cyclone",
        help="Which labeled synthetic scenario to create (default: cyclone).",
    )
    args = parser.parse_args()

    init_database()
    result = run_demo_scenario(args.scenario)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
