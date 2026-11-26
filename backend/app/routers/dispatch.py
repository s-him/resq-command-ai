"""Operator-controlled dispatch-mode settings and simulated deployment ledger API."""

from fastapi import APIRouter, HTTPException, Query, status

from app import auto_dispatch_repository, auto_dispatch_service, dispatch_settings_repository
from app.dispatch_schemas import (
    AutoDispatchResult,
    DispatchAuditList,
    DispatchDeploymentList,
    DispatchSettings,
    DispatchSettingsUpdate,
)
from app.config import auto_dispatch_allowed
from app.event_hub import publish_event

router = APIRouter(prefix="/api/dispatch", tags=["Dispatch Simulation"])

DISCLAIMER = (
    "Simulation only. AUTO creates database assignments and virtual stock reservations; "
    "it never contacts emergency services or sends real vehicles, teams, messages, or supplies."
)


@router.get("/settings", response_model=DispatchSettings)
def get_dispatch_settings() -> dict:
    """Return the persisted MANUAL/AUTO mode, threshold and emergency pause state."""
    return dispatch_settings_repository.get_dispatch_settings()


@router.patch("/settings", response_model=DispatchSettings)
def update_dispatch_settings(payload: DispatchSettingsUpdate) -> dict:
    """Persist operator settings. Enabling AUTO processes eligible open incidents once."""
    if payload.mode is not None and payload.mode.value == "auto" and not auto_dispatch_allowed():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AUTO mode is disabled because every dispatch simulation requires human "
                "approval. Set RESQ_ALLOW_AUTO_DISPATCH=true to enable it for a demo."
            ),
        )
    try:
        settings = dispatch_settings_repository.update_dispatch_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if settings["mode"] == "auto" and not settings["paused"]:
        auto_dispatch_service.dispatch_existing_eligible_incidents()
        auto_dispatch_service.retry_shortfall_dispatches()
    publish_event("dispatch.updated", {"action": "settings_changed", "mode": settings["mode"], "paused": settings["paused"]})
    return settings


@router.get("/deployments", response_model=DispatchDeploymentList)
def list_dispatch_deployments(
    deployment_status: str | None = Query(default=None, alias="status"),
) -> dict:
    if deployment_status not in {None, "deployed", "recalled", "completed"}:
        raise HTTPException(status_code=422, detail="status must be deployed, recalled, or completed.")
    deployments = auto_dispatch_repository.list_deployments(deployment_status)
    return {
        "count": len(deployments),
        "deployments": deployments,
        "disclaimer": DISCLAIMER,
    }


@router.get("/audit", response_model=DispatchAuditList)
def list_dispatch_audit(
    incident_id: int | None = Query(default=None, gt=0),
) -> dict:
    events = auto_dispatch_repository.list_audit_events(incident_id)
    return {
        "count": len(events),
        "events": events,
        "disclaimer": DISCLAIMER,
    }


@router.post(
    "/incidents/{incident_id}/retry",
    response_model=AutoDispatchResult,
)
def retry_incident_shortfall(incident_id: int) -> dict:
    """Retry a previously recorded shortfall using only newly unreserved stock."""
    try:
        result = auto_dispatch_service.auto_dispatch_incident(
            incident_id,
            allow_shortfall_retry=True,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except auto_dispatch_repository.AutoDispatchStockConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.get("attempted"):
        raise HTTPException(status_code=409, detail=result.get("message", "No retry was performed."))
    publish_event("dispatch.updated", {"incident_id": incident_id, "action": "shortfall_retry"})
    return result
