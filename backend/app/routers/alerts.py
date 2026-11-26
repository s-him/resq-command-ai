"""Endpoints for ingesting and reviewing external disaster alerts."""

from fastapi import APIRouter, HTTPException, Query, status

from app import alert_promotion_service, alert_repository, alert_service, incident_repository
from app.alert_schemas import (
    AlertListResponse,
    AlertPromotionResponse,
    AlertReviewRequest,
    AlertReviewStatus,
    AlertSource,
    AlertSourceStatus,
    AlertSyncRequest,
    AlertSyncResponse,
    ExternalAlert,
)
from app.schemas import IncidentCreate

router = APIRouter(prefix="/api/alerts", tags=["External Alerts"])


@router.post("/sync", response_model=AlertSyncResponse)
def sync_external_alerts(request: AlertSyncRequest) -> dict:
    """Manually fetch configured public feeds. This does not create incidents."""
    return alert_service.sync_sources([source.value for source in request.sources])


@router.get("/sources", response_model=list[AlertSourceStatus])
def list_alert_sources() -> list[dict]:
    """Show configured providers and their most recent sync status."""
    return alert_service.list_source_statuses()


@router.get("", response_model=AlertListResponse)
def list_external_alerts(
    source: AlertSource | None = None,
    hazard_type: str | None = Query(default=None, min_length=2, max_length=30),
    alert_level: str | None = Query(default=None, min_length=3, max_length=20),
    review_status: AlertReviewStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List imported alerts with optional source, hazard, level and review filters."""
    alerts, total_count = alert_repository.list_alerts(
        source=source.value if source else None,
        hazard_type=hazard_type.lower() if hazard_type else None,
        alert_level=alert_level.lower() if alert_level else None,
        review_status=review_status.value if review_status else None,
        limit=limit,
        offset=offset,
    )
    return {
        "count": len(alerts),
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "alerts": alerts,
        "disclaimer": alert_service.DISCLAIMER,
    }


@router.post("/{alert_id}/review", response_model=ExternalAlert)
def review_external_alert(alert_id: int, request: AlertReviewRequest) -> dict:
    """Mark an alert reviewed or dismissed; no incident or dispatch is created."""
    alert = alert_repository.review_alert(
        alert_id=alert_id,
        status=request.status.value,
        note=request.note,
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External alert {alert_id} not found.",
        )
    return alert



@router.post(
    "/{alert_id}/promote",
    response_model=AlertPromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
def promote_reviewed_alert(alert_id: int, incident_data: IncidentCreate) -> dict:
    """Create one incident from a reviewed external alert using operator-supplied facts.

    People affected, help needed, incident description, hazard type and location
    are explicitly provided by the operator. Provider data is not used to guess
    these life-safety inputs.
    """
    try:
        incident_id = alert_promotion_service.promote_alert_to_incident(
            alert_id,
            incident_data,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except alert_promotion_service.AlertPromotionConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    alert = alert_repository.get_alert_by_id(alert_id)
    incident = incident_repository.get_incident_by_id(incident_id)
    from app.auto_dispatch_service import try_auto_dispatch_incident

    try_auto_dispatch_incident(incident_id)
    return {
        "alert": alert,
        "incident": incident,
        "message": (
            f"Reviewed external alert #{alert_id} was linked to incident "
            f"#{incident_id}. The incident is now included in the normal priority "
            "and resource-recommendation workflows. If AUTO mode is enabled and the " 
            "incident meets its threshold, a simulated assignment may also be created."
        ),
        "disclaimer": (
            "The incident fields were supplied or confirmed by an operator. "
            "The existing incident severity score is an unvalidated prototype "
            "estimate, not emergency guidance. AUTO may create only a simulated " 
            "database assignment; no external emergency service is contacted."
        ),
    }
