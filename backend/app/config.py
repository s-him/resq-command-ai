"""
Central place for application settings.

Keeping settings in one file means the rest of the code never hard-codes
names, versions or file paths. If something needs to change, change it here.
"""

from pathlib import Path

# Folder that contains this backend (the "backend/" directory).
BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = "Autonomous Multi-Agent Disaster Relief & Emergency Dispatch Engine"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = (
    "Academic prototype for a college mini-project. "
    "Uses sample/manual data only. It is NOT a real emergency system, does not "
    "connect to emergency services, and does not predict disasters. "
    "A human operator must approve or reject every recommendation."
)

# SQLite database file. It is created automatically when the server starts.
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "relief.db"

