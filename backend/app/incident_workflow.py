"""The workflow started by every new incident report.

Monitoring happens while the incident is saved. This module then runs the agent
pipeline and leaves a PENDING recommendation for the operator. Nothing is
approved, reserved or dispatched here unless AUTO simulation has been
explicitly allowed and selected.
"""

import logging

from app import (
    agent_orchestrator,
    incident_repository,
    recommendation_repository,
    recommendations,
    resource_repository,
)
from app.auto_dispatch_service import try_auto_dispatch_incident
from app.event_hub import publish_event

logger = logging.getLogger(__name__)


def start_incident_workflow(incident_id: int) -> None:
    """Best effort: a failure here must never lose the saved incident report."""
    try:
        auto_result = try_auto_dispatch_incident(incident_id)
        if auto_result and auto_result.get("attempted"):
            return

        run = agent_orchestrator.run_incident_pipeline(incident_id)
        publish_event("agents.completed", {"incident_id": incident_id, "run_id": run.get("id")})

        incident = incident_repository.get_incident_by_id(incident_id)
        items, unavailable, insufficient, summary = recommendations.build_recommendation(
            incident, resource_repository.list_available_resources()
        )
        recommendation = recommendation_repository.create_recommendation(
            incident_id=incident_id,
            items=items,
            unavailable_needs=unavailable,
            insufficient_needs=insufficient,
            summary=summary,
        )
        publish_event(
            "recommendations.updated",
            {"incident_id": incident_id, "recommendation_id": recommendation.id},
        )
    except Exception:
        logger.exception("Incident workflow failed for incident %s", incident_id)
