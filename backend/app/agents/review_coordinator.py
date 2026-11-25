"""Combine specialist findings into a conservative human-review queue priority."""

from typing import Any


AGENT_NAME = "review_coordinator"
AGENT_VERSION = "1.0"


def coordinate_review(
    alert: dict[str, Any],
    evidence: dict[str, Any],
    hazard: dict[str, Any],
    recency: dict[str, Any],
    location: dict[str, Any],
) -> dict[str, Any]:
    """Choose a review queue label, never an emergency-response instruction."""
    reasons: list[str] = []
    source = str(alert.get("source") or "").lower()
    level = str(alert.get("alert_level") or "").lower()

    future_timestamp = bool(recency.get("future_timestamp"))
    completeness_grade = evidence.get("completeness_grade")

    if future_timestamp:
        priority = "human_interpretation_required"
        reasons.append("The event timestamp appears to be in the future.")
    elif completeness_grade == "very_limited_completeness":
        priority = "human_interpretation_required"
        reasons.append("Too little evidence is available for even a routine automated queue label.")
    elif source == "gdacs" and level == "red":
        priority = "urgent_review"
        reasons.append("GDACS reports a Red alert level; verify the provider bulletin promptly.")
    elif source == "gdacs" and level == "orange":
        priority = "priority_review"
        reasons.append("GDACS reports an Orange alert level; operator review is recommended.")
    elif source == "gdacs" and level == "green":
        priority = "routine_review"
        reasons.append("GDACS reports a Green alert level; retain for routine operator review.")
    else:
        priority = "human_interpretation_required"
        reasons.append("No cross-hazard review-priority rule is configured for this provider signal.")

    if recency.get("recency_band") == "older_than_one_day":
        reasons.append("The event timestamp is older than one day; check whether the alert remains active.")
    if location.get("location_status") != "coordinates_available":
        reasons.append("Precise coordinates are missing; geographic impact cannot be assessed here.")
    if source == "usgs":
        reasons.append("Earthquake magnitude is not converted into a universal damage or urgency grade.")

    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "completed",
        "review_priority": priority,
        "human_review_required": True,
        "reasons": reasons,
        "decision_boundary": (
            "This is only a queueing aid for a trained human reviewer. It is not an "
            "emergency severity determination, evacuation instruction, or dispatch decision."
        ),
    }
