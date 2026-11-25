"""Evaluate alert evidence completeness without claiming source truth or accuracy."""

from typing import Any


AGENT_NAME = "evidence_quality_agent"
AGENT_VERSION = "1.0"


def evaluate_evidence(alert: dict[str, Any]) -> dict[str, Any]:
    """Measure field completeness; this is not a probability that an alert is true."""
    checks = [
        ("provider_event_id", bool(alert.get("source_event_id")), 15),
        ("event_timestamp", bool(alert.get("event_at")), 20),
        (
            "coordinates",
            alert.get("latitude") is not None and alert.get("longitude") is not None,
            25,
        ),
        ("location_label", bool(alert.get("location") or alert.get("country")), 15),
        ("source_reference", bool(alert.get("source_url")), 10),
        (
            "provider_signal",
            bool(alert.get("alert_level"))
            or alert.get("severity_value") is not None,
            15,
        ),
    ]

    present = []
    missing = []
    score = 0
    for name, is_present, weight in checks:
        if is_present:
            present.append({"field": name, "weight": weight})
            score += weight
        else:
            missing.append(name)

    if score >= 80:
        grade = "high_completeness"
    elif score >= 55:
        grade = "moderate_completeness"
    elif score >= 30:
        grade = "limited_completeness"
    else:
        grade = "very_limited_completeness"

    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "completed",
        "completeness_score": score,
        "completeness_grade": grade,
        "present_evidence": present,
        "missing_evidence": missing,
        "interpretation": (
            "This score measures whether useful fields are present. It does not "
            "measure whether the provider report is true, and it is not a confidence "
            "probability or a measure of disaster severity."
        ),
    }
