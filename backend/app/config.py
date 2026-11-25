"""
Central place for application settings.

Keeping settings in one file means the rest of the code never hard-codes
names, versions or file paths. If something needs to change, change it here.
"""

import os
from pathlib import Path

# Folder that contains this backend (the "backend/" directory).
BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = "Autonomous Multi-Agent Disaster Relief & Emergency Dispatch Engine"
APP_VERSION = "0.8.0"
APP_DESCRIPTION = (
    "Academic prototype for a college mini-project. "
    "Uses manually entered reports and read-only public alerts from GDACS and USGS. "
    "It is NOT a real emergency system, does not connect to emergency services "
    "or dispatch systems, and does not predict disasters. A human operator "
    "must review imported alerts and approve or reject every recommendation."
)

# SQLite database file (project-relative by default; overridable via RELIEF_DATABASE_PATH).
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = Path(os.environ.get("RELIEF_DATABASE_PATH", DATA_DIR / "relief.db"))



def _read_bool(name: str, default: bool) -> bool:
    """Read a conventional environment boolean without failing app startup."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_positive_int(name: str, default: int, minimum: int = 30) -> int:
    """Read a positive interval; invalid or too-small values fall back safely."""
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


# Background provider refresh. Disable with RESQ_ALERT_AUTO_SYNC_ENABLED=false.
ALERT_AUTO_SYNC_ENABLED = _read_bool("RESQ_ALERT_AUTO_SYNC_ENABLED", True)
GDACS_SYNC_INTERVAL_SECONDS = _read_positive_int(
    "RESQ_GDACS_SYNC_INTERVAL_SECONDS", 360
)
USGS_SYNC_INTERVAL_SECONDS = _read_positive_int(
    "RESQ_USGS_SYNC_INTERVAL_SECONDS", 60
)
