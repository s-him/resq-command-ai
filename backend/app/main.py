"""
Entry point of the FastAPI application.

Start the server (from the "backend" folder) with:
    uvicorn app.main:app --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app import alert_service, incident_repository
from app.config import (
    ALERT_AUTO_SYNC_ENABLED,
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    GDACS_SYNC_INTERVAL_SECONDS,
    USGS_SYNC_INTERVAL_SECONDS,
)
from app.database import init_database
from app.errors import validation_error_handler
from app.routers import alerts, assessments, health, incidents, recommendations, resources, response_plans


logger = logging.getLogger(__name__)


async def _run_provider_sync_loop(source: str, interval_seconds: int) -> None:
    """Sync one provider in a worker thread, then wait for its next interval.

    Each provider has its own loop so a slow or failing provider does not
    delay the other provider. Cancellation stops the loop cleanly on shutdown.
    """
    logger.info(
        "Automatic %s alert sync enabled (interval: %s seconds)",
        source.upper(),
        interval_seconds,
    )
    while True:
        try:
            result = await asyncio.to_thread(alert_service.sync_sources, [source])
            source_result = result["sources"][0]
            if source_result["status"] == "failed":
                logger.warning(
                    "Automatic %s sync failed: %s",
                    source.upper(),
                    source_result["error_message"],
                )
            else:
                logger.info(
                    "Automatic %s sync complete: fetched=%s new=%s updated=%s",
                    source.upper(),
                    source_result["fetched_count"],
                    source_result["created_count"],
                    source_result["updated_count"],
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected automatic %s sync error", source.upper())

        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code before `yield` runs when the server starts; code after runs on shutdown."""
    init_database()  # create/upgrade tables
    incident_repository.fill_missing_severity()  # score incidents saved before scoring existed

    sync_tasks = []
    if ALERT_AUTO_SYNC_ENABLED:
        sync_tasks = [
            asyncio.create_task(
                _run_provider_sync_loop("gdacs", GDACS_SYNC_INTERVAL_SECONDS),
                name="gdacs-alert-sync",
            ),
            asyncio.create_task(
                _run_provider_sync_loop("usgs", USGS_SYNC_INTERVAL_SECONDS),
                name="usgs-alert-sync",
            ),
        ]
    else:
        logger.info("Automatic alert synchronization is disabled")

    try:
        yield
    finally:
        for task in sync_tasks:
            task.cancel()
        if sync_tasks:
            await asyncio.gather(*sync_tasks, return_exceptions=True)


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

# Allow the local React dev server (Vite on port 5173) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Return short, readable validation errors instead of FastAPI's default format.
app.add_exception_handler(RequestValidationError, validation_error_handler)

# Register routers (groups of endpoints).
app.include_router(health.router)
app.include_router(alerts.router)
app.include_router(assessments.router)
app.include_router(incidents.router)
app.include_router(resources.router)
app.include_router(recommendations.router)
app.include_router(response_plans.router)


@app.get("/", tags=["Root"])
def root() -> dict:
    """Friendly landing message pointing to the docs and health check."""
    return {
        "message": f"{APP_NAME} is running.",
        "docs": "/docs",
        "health": "/health",
        "incidents": "/api/incidents",
        "alerts": "/api/alerts",
        "priority": "/api/incidents/priority",
        "resources": "/api/resources",
        "response_plans": "/api/response-plans",
        "agent_trace": "/api/incidents/{incident_id}/agent-trace",
    }

