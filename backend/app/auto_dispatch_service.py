"""Policy-gated automatic dispatch orchestration for simulation only."""

import logging
from typing import Any

from app import (
    agent_orchestrator,
    auto_dispatch_repository,
    dispatch_settings_repository,
    incident_repository,
    recommendations,
    resource_repository,
)
from app.schemas import InsufficientNeed, UnavailableNeed

logger = logging.getLogger(__name__)


def _qualifies(incident, minimum_severity: str) -> bool:
    level = incident.severity.level.value
    if minimum_severity == "Critical":
        return level == "Critical"
    return level in {"High", "Critical"}


def _top_up_items(incident, items, unavailable_needs, insufficient_needs):
    """Subtract already deployed units so shortfall retries request only remaining need."""
    already_deployed = auto_dispatch_repository.get_active_deployed_quantities(incident.id)
    grouped = recommendations.group_needs_by_resource_type(incident.help_needed)

    selected_items = []
    next_unavailable = []
    next_insufficient = []

    for resource_type, help_needed in grouped.items():
        total_needed = recommendations.desired_quantity_for(
            resource_type, incident.people_affected
        )
        remaining_need = max(
            0, total_needed - already_deployed.get(resource_type.value, 0)
        )
        if remaining_need == 0:
            continue

        candidates = [item for item in items if item.resource_type == resource_type]
        allocated = 0
        for item in candidates:
            if allocated >= remaining_need:
                break
            quantity = min(item.recommended_quantity, remaining_need - allocated)
            if quantity <= 0:
                continue
            selected_items.append(
                item.model_copy(
                    update={
                        "recommended_quantity": quantity,
                        "explanation": (
                            item.explanation
                            + f" AUTO top-up: {quantity} additional unit(s) assigned "
                            "after subtracting earlier active deployments."
                        ),
                    }
                )
            )
            allocated += quantity

        shortfall = remaining_need - allocated
        if shortfall <= 0:
            continue
        if allocated == 0 and already_deployed.get(resource_type.value, 0) == 0:
            next_unavailable.append(
                UnavailableNeed(
                    help_needed=help_needed,
                    resource_type=resource_type,
                    message=(
                        f"No currently unreserved '{resource_type.value}' resource "
                        f"was available for {', '.join(item.value for item in help_needed)}."
                    ),
                )
            )
        else:
            next_insufficient.append(
                InsufficientNeed(
                    help_needed=help_needed,
                    resource_type=resource_type,
                    estimated_needed=total_needed,
                    available_matched=total_needed - shortfall,
                    shortfall=shortfall,
                    message=(
                        f"Additional '{resource_type.value}' stock is still required: "
                        f"{shortfall} unit(s) short after active assignments."
                    ),
                )
            )

    return selected_items, next_unavailable, next_insufficient


def auto_dispatch_incident(
    incident_id: int,
    *,
    allow_shortfall_retry: bool = False,
) -> dict[str, Any]:
    """Run agents, calculate a recommendation and atomically reserve auto assignments."""
    settings = dispatch_settings_repository.get_dispatch_settings()
    if settings["mode"] != "auto":
        return {
            "incident_id": incident_id,
            "attempted": False,
            "dispatched": False,
            "message": "Dispatch mode is MANUAL; no automatic assignment was created.",
        }
    if settings["paused"]:
        return {
            "incident_id": incident_id,
            "attempted": False,
            "dispatched": False,
            "message": "Automatic dispatch is paused by the emergency kill switch.",
        }

    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise LookupError(f"Incident {incident_id} not found.")
    if incident.status.value != "open":
        return {
            "incident_id": incident_id,
            "attempted": False,
            "dispatched": False,
            "message": "Only open incidents are eligible for automatic dispatch.",
        }
    if not _qualifies(incident, settings["minimum_severity"]):
        return {
            "incident_id": incident_id,
            "attempted": False,
            "dispatched": False,
            "message": (
                f"Incident severity does not meet the configured "
                f"{settings['minimum_severity']} threshold."
            ),
        }

    if allow_shortfall_retry:
        latest = auto_dispatch_repository.latest_audit_event(incident_id)
        if latest is None or latest["action"] not in {"shortfall", "partial_shortfall"}:
            return {
                "incident_id": incident_id,
                "attempted": False,
                "dispatched": False,
                "message": "No retryable shortfall exists for this incident; no additional assignment was created.",
            }
    elif auto_dispatch_repository.has_auto_dispatch_history(incident_id):
        return {
            "incident_id": incident_id,
            "attempted": False,
            "dispatched": False,
            "message": "This incident already has an automatic-dispatch attempt.",
        }

    # Run the five named agents first. Their output is advisory; allocation remains
    # determined by the existing validated recommendation matcher.
    agent_orchestrator.run_incident_pipeline(incident_id)
    resources = resource_repository.list_available_resources()
    items, unavailable, insufficient, summary = recommendations.build_recommendation(
        incident, resources
    )
    if allow_shortfall_retry:
        items, unavailable, insufficient = _top_up_items(
            incident, items, unavailable, insufficient
        )

    return auto_dispatch_repository.create_auto_dispatch(
        incident=incident,
        items=items,
        unavailable_needs=unavailable,
        insufficient_needs=insufficient,
        summary=summary,
        allow_shortfall_retry=allow_shortfall_retry,
        actor="system-auto",
    )


def try_auto_dispatch_incident(incident_id: int) -> dict[str, Any] | None:
    """Best-effort trigger called after a newly saved incident or alert promotion."""
    try:
        return auto_dispatch_incident(incident_id)
    except Exception:
        logger.exception("Automatic dispatch simulation failed for incident %s", incident_id)
        return None


def dispatch_existing_eligible_incidents() -> list[dict[str, Any]]:
    """When AUTO is enabled, process existing open incidents in deterministic order."""
    from app import prioritization

    ranked = prioritization.rank_incidents(incident_repository.list_open_incidents())
    results = []
    for item in ranked:
        result = try_auto_dispatch_incident(item.id)
        if result is not None and result.get("attempted"):
            results.append(result)
    return results


def retry_shortfall_dispatches() -> list[dict[str, Any]]:
    """Top up previously short incidents after new or increased stock is registered."""
    results = []
    for incident_id in auto_dispatch_repository.list_shortfall_incident_ids():
        try:
            result = auto_dispatch_incident(
                incident_id,
                allow_shortfall_retry=True,
            )
            if result.get("attempted"):
                results.append(result)
        except Exception:
            logger.exception("Shortfall retry failed for incident %s", incident_id)
    return results
