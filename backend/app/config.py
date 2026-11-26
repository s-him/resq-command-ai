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
APP_VERSION = "0.10.0"
APP_DESCRIPTION = (
    "Academic prototype for a college mini-project. "
    "Uses manually entered reports and read-only public alerts from GDACS and USGS. "
    "It is NOT a real emergency system, does not connect to emergency services "
    "or dispatch systems, and does not predict disasters. A human operator "
    "must review external alerts before promotion. MANUAL mode requires operator decisions; AUTO mode creates virtual assignments only."
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


def _read_positive_float(name: str, default: float, minimum: float = 0.1) -> float:
    """Read a positive float; malformed or unsafe values use the default."""
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def get_llm_settings() -> dict[str, object]:
    """Return runtime LLM settings; defaults keep the application fully offline."""
    return {
        "enabled": _read_bool("LLM_ENABLED", False),
        "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip(),
        "api_key": os.environ.get("LLM_API_KEY", "").strip(),
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini").strip(),
        "timeout_seconds": _read_positive_float("LLM_TIMEOUT_SECONDS", 8.0),
    }
