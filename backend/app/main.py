"""
Entry point of the FastAPI application.

Start the server (from the "backend" folder) with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app import incident_repository
from app.config import APP_DESCRIPTION, APP_NAME, APP_VERSION
from app.database import init_database
from app.errors import validation_error_handler
from app.routers import alerts, assessments, health, incidents, recommendations, resources, response_plans


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code before `yield` runs when the server starts; code after runs on shutdown."""
    init_database()  # create/upgrade tables
    incident_repository.fill_missing_severity()  # score incidents saved before scoring existed
    yield


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
    }

