"""Describe available location evidence without fabricating population exposure."""

from typing import Any


AGENT_NAME = "location_evidence_agent"
AGENT_VERSION = "1.0"


def evaluate_location(alert: dict[str, Any]) -> dict[str, Any]:
    latitude = alert.get("latitude")
    longitude = alert.get("longitude")
    has_coordinates = latitude is not None and longitude is not None

    if has_coordinates:
        location_status = "coordinates_available"
        location_summary = f"Coordinates: {latitude}, {longitude}"
    elif alert.get("location") or alert.get("country"):
        location_status = "text_location_only"
        location_summary = alert.get("location") or alert.get("country")
    else:
        location_status = "location_missing"
        location_summary = "The provider did not supply a usable point or location label."

    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "completed" if has_coordinates or location_summary else "insufficient_data",
        "location_status": location_status,
        "latitude": latitude,
        "longitude": longitude,
        "location_summary": location_summary,
        "population_exposure": "unknown",
        "population_exposure_reason": (
            "No population, settlement, infrastructure, or exposure dataset is connected yet. "
            "Affected people must not be estimated from coordinates alone."
        ),
        "limitations": [
            "Coordinates identify a reported point, not a validated impact boundary.",
            "No reverse geocoding or affected-area polygon analysis is performed.",
        ],
    }
