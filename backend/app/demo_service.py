"""Deterministic synthetic scenarios for demos and local acceptance checks.

Demo records are permanently labeled SIMULATED and use stable provider event IDs,
so rerunning a scenario updates its alert snapshots instead of duplicating records.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from app import (
    agent_orchestrator,
    alert_promotion_service,
    alert_repository,
    auto_dispatch_repository,
    auto_dispatch_service,
    dispatch_settings_repository,
    incident_repository,
    prioritization,
    recommendation_repository,
    recommendations,
    resource_repository,
)
from app.alert_sources import NormalizedAlert
from app.event_hub import publish_event
from app.schemas import (
    AvailabilityStatus,
    HazardType,
    HelpType,
    IncidentCreate,
    ResourceCreate,
    ResourceType,
    ResourceUpdate,
)


DISCLAIMER = (
    "SIMULATED DEMO DATA ONLY. Locations, people counts, provider alerts and resource "
    "inventory in this scenario are synthetic examples, not current hazard reports. "
    "AUTO creates virtual database assignments only; no emergency service, responder, "
    "vehicle, message or physical stock is contacted or moved."
)

_HELP_TYPES = [
    HelpType.RESCUE,
    HelpType.MEDICAL,
    HelpType.EVACUATION,
    HelpType.SHELTER,
    HelpType.FOOD,
    HelpType.WATER,
]

_SCENARIOS: dict[str, dict[str, Any]] = {
    "cyclone": {
        "source": "gdacs",
        "event_type": "TC",
        "hazard_type": HazardType.CYCLONE,
        "unit": "km/h",
        "events": [
            {
                "title": "Coastal Cyclone — Paradip sector",
                "location": "Paradip coastal belt, Odisha",
                "description": "SIMULATED cyclone impact with coastal wind damage and evacuation needs.",
                "people": 14500,
                "level": "red",
                "value": 185.0,
                "latitude": 20.3166,
                "longitude": 86.6111,
            },
            {
                "title": "Coastal Cyclone — Puri sector",
                "location": "Puri coastal belt, Odisha",
                "description": "SIMULATED storm surge and wind exposure near coastal settlements.",
                "people": 7600,
                "level": "orange",
                "value": 155.0,
                "latitude": 19.8135,
                "longitude": 85.8312,
            },
            {
                "title": "Coastal Cyclone — Ganjam sector",
                "location": "Ganjam coast, Odisha",
                "description": "SIMULATED heavy wind and localized infrastructure disruption.",
                "people": 3100,
                "level": "green",
                "value": 125.0,
                "latitude": 19.3149,
                "longitude": 84.7941,
            },
        ],
        "resources": [
            (ResourceType.RESCUE_TEAM, "Rescue Teams", 55, "Paradip Demo Depot", 20.30, 86.60),
            (ResourceType.AMBULANCE, "Ambulance Pool", 110, "Puri Demo Depot", 19.81, 85.83),
            (ResourceType.SHELTER, "Shelter Places", 50000, "Puri Demo Shelter", 19.80, 85.82),
            (ResourceType.SUPPLY, "Relief Supply Kits", 50000, "Ganjam Demo Depot", 19.31, 84.79),
        ],
    },
    "flood": {
        "source": "gdacs",
        "event_type": "FL",
        "hazard_type": HazardType.FLOOD,
        "unit": "m",
        "events": [
            {
                "title": "River Flood — Barpeta sector",
                "location": "Barpeta floodplain, Assam",
                "description": "SIMULATED river flooding with deep water and evacuation needs.",
                "people": 9800,
                "level": "red",
                "value": 2.3,
                "latitude": 26.3226,
                "longitude": 91.0063,
            },
            {
                "title": "River Flood — Dhemaji sector",
                "location": "Dhemaji floodplain, Assam",
                "description": "SIMULATED inundation affecting homes and access roads.",
                "people": 4300,
                "level": "orange",
                "value": 1.2,
                "latitude": 27.4800,
                "longitude": 94.5800,
            },
            {
                "title": "River Flood — Majuli sector",
                "location": "Majuli river island, Assam",
                "description": "SIMULATED localized flooding with shelter and supply needs.",
                "people": 2100,
                "level": "green",
                "value": 0.7,
                "latitude": 26.9500,
                "longitude": 94.2100,
            },
        ],
        "resources": [
            (ResourceType.RESCUE_TEAM, "Rescue Teams", 36, "Barpeta Demo Depot", 26.32, 91.01),
            (ResourceType.AMBULANCE, "Ambulance Pool", 72, "Dhemaji Demo Depot", 27.48, 94.58),
            (ResourceType.SHELTER, "Shelter Places", 50000, "Barpeta Demo Shelter", 26.33, 91.00),
            (ResourceType.SUPPLY, "Relief Supply Kits", 50000, "Majuli Demo Depot", 26.95, 94.21),
        ],
    },
    "earthquake": {
        "source": "usgs",
        "event_type": "earthquake",
        "hazard_type": HazardType.EARTHQUAKE,
        "unit": "magnitude",
        "events": [
            {
                "title": "Earthquake — Guwahati sector",
                "location": "Guwahati, Assam",
                "description": "SIMULATED strong ground shaking with structural inspection and rescue needs.",
                "people": 8200,
                "level": "red",
                "value": 6.7,
                "latitude": 26.1445,
                "longitude": 91.7362,
            },
            {
                "title": "Earthquake — Shillong sector",
                "location": "Shillong, Meghalaya",
                "description": "SIMULATED strong tremor with medical and shelter requirements.",
                "people": 3500,
                "level": "orange",
                "value": 5.6,
                "latitude": 25.5788,
                "longitude": 91.8933,
            },
            {
                "title": "Earthquake — Tezpur sector",
                "location": "Tezpur, Assam",
                "description": "SIMULATED moderate tremor with localized response needs.",
                "people": 1500,
                "level": "green",
                "value": 4.8,
                "latitude": 26.6336,
                "longitude": 92.8000,
            },
        ],
        "resources": [
            (ResourceType.RESCUE_TEAM, "Rescue Teams", 30, "Guwahati Demo Depot", 26.14, 91.74),
            (ResourceType.AMBULANCE, "Ambulance Pool", 60, "Shillong Demo Depot", 25.58, 91.89),
            (ResourceType.SHELTER, "Shelter Places", 50000, "Guwahati Demo Shelter", 26.15, 91.73),
            (ResourceType.SUPPLY, "Relief Supply Kits", 50000, "Tezpur Demo Depot", 26.63, 92.80),
        ],
    },
}


def _build_alerts(scenario: str, definition: dict[str, Any], now: datetime) -> list[NormalizedAlert]:
    alerts = []
    for index, item in enumerate(definition["events"], start=1):
        event_at = now - timedelta(minutes=8 + index * 24)
        magnitude = float(item["value"])
        alerts.append(
            NormalizedAlert(
                source=definition["source"],
                source_event_id=f"RESQ-DEMO-{scenario.upper()}-{index:02d}",
                event_type=definition["event_type"],
                hazard_type=definition["hazard_type"].value,
                title=f"SIMULATED · {item['title']}",
                description=item["description"],
                location=item["location"],
                country="India",
                alert_level=item["level"],
                alert_score={"red": 0.95, "orange": 0.72, "green": 0.38}[item["level"]],
                severity_value=magnitude,
                severity_unit=definition["unit"],
                severity_text=f"{magnitude:g} {definition['unit']}",
                latitude=item["latitude"],
                longitude=item["longitude"],
                depth_km=None,
                event_at=event_at.isoformat(),
                source_updated_at=now.isoformat(),
                source_url=None,
                raw_data={
                    "label": "SIMULATED",
                    "scenario": scenario,
                    "sample_index": index,
                    "synthetic": True,
                },
            )
        )
    return alerts


def _ensure_demo_resources(scenario: str, definition: dict[str, Any]) -> int:
    """Create demo pools and reconcile legacy sizes without breaking active assignments."""
    existing_resources = {
        resource.name: resource for resource in resource_repository.list_resources()
    }
    created = 0
    for resource_type, label, quantity, location, latitude, longitude in definition["resources"]:
        name = f"SIMULATED · {scenario.upper()} · {label}"
        existing = existing_resources.get(name)
        if existing is not None:
            # Reconcile old oversized pools, while preserving active virtual assignments.
            active_reserved = max(
                existing.simulation_reserved_quantity or 0,
                existing.deployed_quantity or 0,
            )
            target_quantity = max(quantity, active_reserved)
            if existing.quantity_available != target_quantity:
                resource_repository.update_resource(
                    existing.id,
                    ResourceUpdate(
                        quantity_available=target_quantity,
                        note=(
                            "SIMULATED demo inventory reconciled to the documented "
                            "scenario capacity; active virtual assignments preserved."
                        ),
                    ),
                )
            continue

        resource_repository.create_resource(
            ResourceCreate(
                resource_type=resource_type,
                name=name,
                quantity_available=quantity,
                location=f"SIMULATED · {location}",
                availability_status=AvailabilityStatus.AVAILABLE,
                latitude=latitude,
                longitude=longitude,
            )
        )
        created += 1
    return created


def _create_pending_recommendation(incident_id: int) -> None:
    incident = incident_repository.get_incident_by_id(incident_id)
    items, unavailable, insufficient, summary = recommendations.build_recommendation(
        incident, resource_repository.list_available_resources()
    )
    recommendation_repository.create_recommendation(
        incident_id=incident_id,
        items=items,
        unavailable_needs=unavailable,
        insufficient_needs=insufficient,
        summary=summary,
    )


def run_demo_scenario(scenario: str) -> dict[str, Any]:
    """Create/update one synthetic alert scenario and run the normal incident workflow."""
    if scenario not in _SCENARIOS:
        raise ValueError("scenario must be cyclone, flood, or earthquake")

    definition = _SCENARIOS[scenario]
    now = datetime.now(timezone.utc)
    normalized_alerts = _build_alerts(scenario, definition, now)
    alerts_created, alerts_updated = alert_repository.upsert_alerts(
        definition["source"],
        [item.to_dict() for item in normalized_alerts],
    )
    rows, _ = alert_repository.list_alerts(
        source=definition["source"],
        limit=500,
        offset=0,
    )
    rows_by_event_id = {item["source_event_id"]: item for item in rows}

    resources_created = _ensure_demo_resources(scenario, definition)
    incident_ids: list[int] = []
    incidents_created = 0

    for index, event in enumerate(definition["events"], start=1):
        event_id = f"RESQ-DEMO-{scenario.upper()}-{index:02d}"
        alert = rows_by_event_id.get(event_id)
        if alert is None:
            raise RuntimeError(f"Demo alert {event_id} could not be loaded after upsert.")

        incident_id = alert.get("linked_incident_id")
        if incident_id is None:
            alert_repository.review_alert(
                alert["id"],
                status="reviewed",
                note="SIMULATED demo flow: automatically reviewed for demonstration only.",
            )
            reported_at = now - timedelta(minutes=6 + index * 24)
            incident_data = IncidentCreate(
                hazard_type=definition["hazard_type"],
                description=f"SIMULATED demo report: {event['description']}",
                location=f"SIMULATED · {event['location']}",
                reported_at=reported_at,
                event_at=reported_at,
                people_affected=event["people"],
                help_needed=_HELP_TYPES,
                latitude=event["latitude"],
                longitude=event["longitude"],
                hazard_magnitude=float(event["value"]),
                hazard_magnitude_unit=definition["unit"],
                provider_alert_level=event["level"],
            )
            try:
                incident_id = alert_promotion_service.promote_alert_to_incident(
                    alert["id"],
                    incident_data,
                )
                incidents_created += 1
                publish_event("incidents.updated", {"incident_id": incident_id, "action": "demo_created"})
            except alert_promotion_service.AlertAlreadyPromoted:
                refreshed = alert_repository.get_alert_by_id(alert["id"])
                incident_id = refreshed.get("linked_incident_id") if refreshed else None

        if incident_id is None:
            continue
        incident_id = int(incident_id)
        incident = incident_repository.get_incident_by_id(incident_id)
        if incident is None:
            continue
        incident_ids.append(incident_id)

    settings = dispatch_settings_repository.get_dispatch_settings()
    dispatch_results = []
    agent_runs = 0
    for incident_id in incident_ids:
        auto_result = auto_dispatch_service.try_auto_dispatch_incident(incident_id)
        reused = False
        needs_recommendation = not recommendation_repository.list_recommendations_for_incident(
            incident_id
        )
        if auto_result and auto_result.get("attempted"):
            agent_runs += 1  # AUTO already ran the five-agent pipeline.
            result = auto_result
        else:
            agent_run = agent_orchestrator.run_incident_pipeline(incident_id)
            agent_runs += 1
            publish_event(
                "agents.completed",
                {"incident_id": incident_id, "run_id": agent_run.get("id"), "source": "demo"},
            )
            if needs_recommendation:
                _create_pending_recommendation(incident_id)
            active_quantities = auto_dispatch_repository.get_active_deployed_quantities(incident_id)
            reused = settings["mode"] == "auto" and any(active_quantities.values())
            result = {
                "attempted": False,
                "dispatched": reused,
                "plan_id": None,
                "message": (
                    "Existing virtual assignments remain active; no duplicate dispatch was created."
                    if reused
                    else (
                        auto_result.get("message", "No automatic assignment was created.")
                        if auto_result
                        else "Automatic dispatch did not run; see dispatch mode and threshold settings."
                    )
                ),
            }
        dispatch_results.append(
            {
                "incident_id": incident_id,
                "attempted": bool(result.get("attempted")),
                "dispatched": bool(result.get("dispatched")),
                "reused": reused,
                "plan_id": result.get("plan_id"),
                "message": result.get("message", "No automatic assignment was created."),
            }
        )

    ranked = prioritization.rank_incidents(incident_repository.list_open_incidents())
    priority_order = [item.id for item in ranked]
    dispatched_count = sum(1 for item in dispatch_results if item["dispatched"])
    newly_dispatched_count = sum(
        1 for item in dispatch_results if item["dispatched"] and item["attempted"]
    )
    reused_count = sum(1 for item in dispatch_results if item["reused"])

    publish_event(
        "alerts.updated",
        {"scenario": scenario, "created_count": alerts_created, "updated_count": alerts_updated},
    )
    publish_event(
        "resources.updated",
        {"scenario": scenario, "created_count": resources_created},
    )
    publish_event(
        "demo.updated",
        {
            "scenario": scenario,
            "incident_ids": incident_ids,
            "dispatch_mode": settings["mode"],
            "dispatched_count": dispatched_count,
        },
    )

    if settings["mode"] == "auto":
        if reused_count and newly_dispatched_count:
            message = (
                f"SIMULATED {scenario} scenario processed: {len(incident_ids)} incident(s), "
                f"{newly_dispatched_count} new and {reused_count} existing active virtual assignment(s) reused."
            )
        elif reused_count:
            message = (
                f"SIMULATED {scenario} scenario refreshed: {reused_count} existing active virtual assignment(s) "
                "reused; no duplicate dispatch was created."
            )
        elif newly_dispatched_count:
            message = (
                f"SIMULATED {scenario} scenario processed: {len(incident_ids)} incident(s), "
                f"{agent_runs} agent run(s), {newly_dispatched_count} virtual automatic assignment(s)."
            )
        else:
            message = (
                f"SIMULATED {scenario} scenario processed, but no automatic assignment was made. "
                "Check the severity threshold, pause switch and demo resource inventory."
            )
    else:
        message = (
            f"SIMULATED {scenario} scenario created {alerts_created} alert(s) and "
            f"{incidents_created} incident(s). New recommendations are waiting for "
            "operator approval."
        )

    return {
        "scenario": scenario,
        "dispatch_mode": settings["mode"],
        "alerts_created": alerts_created,
        "alerts_updated": alerts_updated,
        "incidents_created": incidents_created,
        "resources_created": resources_created,
        "incident_ids": incident_ids,
        "priority_order": priority_order,
        "agent_runs": agent_runs,
        "dispatched_count": dispatched_count,
        "dispatch_results": dispatch_results,
        "message": message,
        "disclaimer": DISCLAIMER,
    }
