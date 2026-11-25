"""
Incident endpoints.

POST /api/incidents                        -> validate, score and save a new incident report
GET  /api/incidents                        -> list all saved incidents (any status)
GET  /api/incidents/priority               -> open incidents only, highest priority first
GET  /api/incidents/{id}                   -> retrieve one incident by ID
POST /api/incidents/{id}/recommendation    -> generate and save a pending resource suggestion
GET  /api/incidents/{id}/history           -> list recommendations and operator decisions for an incident
"""

from fastapi import APIRouter, HTTPException, status

from app import (
    incident_lifecycle_repository,
    incident_repository,
    prioritization,
    recommendation_repository,
    recommendations,
    resource_repository,
)
from app.schemas import (\n    Incident,\n    IncidentCreate,\n    IncidentHistory,\n    IncidentOperatorNote,\n    IncidentStatusUpdate,\n    IncidentUpdateEntry,\n    IncidentUpdateList,\n    PriorityList,\n    Recommendation,\n)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.post("", response_model=Incident, status_code=status.HTTP_201_CREATED)
def create_incident(incident: IncidentCreate) -> Incident:
    """Create an incident report. It is saved with a new ID, status "open",
    and a rule-based severity score (an unvalidated prototype estimate).

    By the time this function runs, FastAPI has already validated the request
    body against IncidentCreate, so `incident` is guaranteed to be valid.
    """
    return incident_repository.create_incident(incident)


@router.get("", response_model=list[Incident])
def list_incidents() -> list[Incident]:
    """Return all saved incidents (oldest first), each with its saved severity."""
    return incident_repository.list_incidents()


@router.get("/priority", response_model=PriorityList)
def list_open_incidents_by_priority() -> PriorityList:
    """Return open incidents ordered by priority, highest first.

    Order: severity score (high first), then people affected (more first),
    then reported_at (older first), then ID. Each incident includes its rank
    and a short explanation. Resolved and closed incidents are not included.
    """
    ranked = prioritization.rank_incidents(incident_repository.list_open_incidents())
    return PriorityList(
        ranking_rules=prioritization.RANKING_RULES,
        disclaimer=prioritization.DISCLAIMER,
        count=len(ranked),
        incidents=ranked,
    )


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: int) -> Incident:
    """Return a single saved incident by ID, or 404 if it does not exist."""
    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )
    return incident


@router.post(
    "/{incident_id}/recommendation",
    response_model=Recommendation,
    status_code=status.HTTP_201_CREATED,
)
def generate_incident_recommendation(incident_id: int) -> Recommendation:
    """Generate and save a pending resource recommendation for an incident.

    Matches the incident's help_needed list against available resources with
    positive quantity. Does NOT reduce resource quantities; a human operator
    must review and approve or reject the suggestion.
    """
    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )

    available_resources = resource_repository.list_available_resources()
    items, unavailable_needs, insufficient_needs, summary = recommendations.build_recommendation(
        incident, available_resources
    )
    return recommendation_repository.create_recommendation(
        incident_id=incident.id,
        items=items,
        unavailable_needs=unavailable_needs,
        insufficient_needs=insufficient_needs,
        summary=summary,
    )


@router.get("/{incident_id}/history", response_model=IncidentHistory)
def get_incident_history(incident_id: int) -> IncidentHistory:
    """Return all saved recommendations and operator decision history for an incident."""
    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )

    return IncidentHistory(
        incident_id=incident.id,
        recommendations=recommendation_repository.list_recommendations_for_incident(incident.id),
        action_history=recommendation_repository.list_action_history_for_incident(incident.id),
    )



@router.patch("/{incident_id}/status", response_model=Incident)
def update_incident_status(
    incident_id: int,
    request: IncidentStatusUpdate,
) -> Incident:
    """Move an incident through the operator-managed lifecycle."""
    try:
        event = incident_lifecycle_repository.change_incident_status(
            incident_id=incident_id,
            new_status=request.status,
            note=request.note,
        )
    except incident_lifecycle_repository.IncidentLifecycleConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )
    return incident_repository.get_incident_by_id(incident_id)


@router.post(
    "/{incident_id}/updates",
    response_model=IncidentUpdateEntry,
    status_code=status.HTTP_201_CREATED,
)
def add_incident_operator_update(
    incident_id: int,
    request: IncidentOperatorNote,
) -> dict:
    """Append an operational note to the incident timeline."""
    try:
        event = incident_lifecycle_repository.add_operator_note(
            incident_id=incident_id,
            note=request.note,
        )
    except incident_lifecycle_repository.IncidentLifecycleConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )
    return event


@router.get("/{incident_id}/updates", response_model=IncidentUpdateList)
def get_incident_operational_updates(incident_id: int) -> dict:
    """Return status changes and operator notes for an incident."""
    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )

    updates = incident_lifecycle_repository.list_incident_updates(incident_id)
    return {
        "incident_id": incident_id,
        "count": len(updates),
        "active_simulation_count": incident_lifecycle_repository.count_active_simulations(
            incident_id
        ),
        "updates": updates,
        "disclaimer": (
            "Operational updates are operator-entered prototype audit records. "
            "They do not verify real-world conditions or confirm that response "
            "teams have physically arrived."
        ),
    }
