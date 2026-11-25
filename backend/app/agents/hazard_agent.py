"""Interpret provider-native hazard signals without inventing universal severity."""

from typing import Any


AGENT_NAME = "hazard_signal_agent"
AGENT_VERSION = "1.0"


def evaluate_hazard_signal(alert: dict[str, Any]) -> dict[str, Any]:
    source = str(alert.get("source") or "").lower()
    hazard_type = str(alert.get("hazard_type") or "unknown").lower()

    if source == "gdacs":
        level = str(alert.get("alert_level") or "").lower()
        signal_map = {
            "red": ("red_provider_alert", "The provider marks this event Red."),
            "orange": ("orange_provider_alert", "The provider marks this event Orange."),
            "green": ("green_provider_alert", "The provider marks this event Green."),
        }
        signal, explanation = signal_map.get(
            level,
            (
                "provider_level_unavailable",
                "GDACS alert level is missing or unrecognized; human interpretation is required.",
            ),
        )
        return {
            "agent": AGENT_NAME,
            "version": AGENT_VERSION,
            "status": "completed",
            "hazard_type": hazard_type,
            "provider": "gdacs",
            "provider_alert_level": level or None,
            "provider_alert_score": alert.get("alert_score"),
            "signal": signal,
            "severity_value": alert.get("severity_value"),
            "severity_unit": alert.get("severity_unit"),
            "explanation": explanation,
            "limitations": [
                "The GDACS level is retained as the provider's own signal.",
                "It is not converted into a locally validated damage or life-safety score.",
            ],
        }

    if source == "usgs" and hazard_type == "earthquake":
        return {
            "agent": AGENT_NAME,
            "version": AGENT_VERSION,
            "status": "completed",
            "hazard_type": hazard_type,
            "provider": "usgs",
            "magnitude": alert.get("severity_value"),
            "magnitude_unit": alert.get("severity_unit") or "magnitude",
            "depth_km": alert.get("depth_km"),
            "signal": "earthquake_magnitude_reported",
            "explanation": (
                "USGS magnitude and depth are shown as reported. Magnitude alone "
                "does not establish local damage or human impact."
            ),
            "limitations": [
                "No universal risk grade is assigned from magnitude alone.",
                "Local impact also depends on depth, distance, soil, buildings, and exposure.",
                "Population exposure and building vulnerability are not available in this stage.",
            ],
        }

    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "completed",
        "hazard_type": hazard_type,
        "provider": source or None,
        "signal": "human_interpretation_required",
        "explanation": "No validated hazard-specific interpretation rule is configured for this source and event type.",
        "limitations": ["Do not infer local severity from the available fields alone."],
    }
