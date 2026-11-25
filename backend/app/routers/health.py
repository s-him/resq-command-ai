"""
Health-check endpoint.

A health check is a simple URL that tells you "the server is running".
It also reports whether the SQLite database can be reached.
"""

from fastapi import APIRouter

from app.config import APP_NAME, APP_VERSION
from app.database import is_database_ok

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    """Return the status of the API and the database."""
    database_ok = is_database_ok()
    return {
        "status": "ok" if database_ok else "degraded",
        "app": APP_NAME,
        "version": APP_VERSION,
        "database": "connected" if database_ok else "unavailable",
        "mode": "academic-prototype",
    }

