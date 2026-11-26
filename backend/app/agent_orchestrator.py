"""Run and persist the incident-level multi-agent review pipeline."""

from time import perf_counter
from typing import Any

from app import alert_repository, incident_repository, resource_repository
from app.agents import (
    AgentResult,
    NotificationAgent,
    MonitoringAgent,
    ResourceAllocationAgent,
    PrioritizationAgent,
    SeverityAgent,
)
from app.agent_trace_repository import save_agent_trace
from app.llm.client import LLMClient
from app.schemas import Incident, Resource

ENGINE_VERSION = "incident-agents-v2"


def _dump_incident(item: Incident) -> dict[str, Any]:
    return item.model_dump(mode="json")


def run_incident_pipeline(
    incident_id: int,
    *,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """Execute all five agents in order and save their complete trace.

    The LLM can add advisory classification or narrative suggestions. Deterministic
    severity, prioritization and stock matching remain the source of truth.
    This function never creates/updates incidents, recommendations, plans,
    inventory quantities, or dispatch states.
    """
    started = perf_counter()
    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise LookupError(f"Incident {incident_id} not found.")

    shared_client = llm_client if llm_client is not None else LLMClient()
    open_incidents = incident_repository.list_open_incidents()
    available_resources = resource_repository.list_available_resources()
    normalized_alert = alert_repository.get_alert_linked_to_incident(incident_id)
    context = {
        "incident": _dump_incident(incident),
        "normalized_source_alert": normalized_alert,
        "open_incidents": [_dump_incident(item) for item in open_incidents],
        "available_resources": [
            item.model_dump(mode="json") if isinstance(item, Resource) else item
            for item in available_resources
        ],
    }

    agents = [
        MonitoringAgent(shared_client),
        SeverityAgent(shared_client),
        PrioritizationAgent(shared_client),
        ResourceAllocationAgent(shared_client),
        NotificationAgent(shared_client),
    ]
    results: list[AgentResult] = []
    for agent in agents:
        agent_context = {**context, "agent_results": list(results)}
        results.append(agent.run(agent_context))

    notification_output = results[-1].output
    summary = str(notification_output["summary"])
    duration_ms = max(0, round((perf_counter() - started) * 1000))
    inputs_summary = {
        "incident_id": incident.id,
        "hazard_type": incident.hazard_type.value,
        "location": incident.location,
        "people_affected_reported": incident.people_affected,
        "incident_status": incident.status.value,
        "open_incident_count": len(open_incidents),
        "available_resource_pool_count": len(available_resources),
        "source": normalized_alert.get("source") if normalized_alert else "manual_or_operator_entered_incident",
        "linked_alert_id": normalized_alert.get("id") if normalized_alert else None,
    }
    return save_agent_trace(
        incident_id=incident.id,
        inputs_summary=inputs_summary,
        agents=results,
        summary=summary,
        engine_version=ENGINE_VERSION,
        duration_ms=duration_ms,
    )
