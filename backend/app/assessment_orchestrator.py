"""Run the specialist agents and combine their explainable outputs."""

from datetime import datetime, timezone
from typing import Any

from app.agents.evidence_agent import evaluate_evidence
from app.agents.hazard_agent import evaluate_hazard_signal
from app.agents.location_agent import evaluate_location
from app.agents.recency_agent import evaluate_recency
from app.agents.review_coordinator import coordinate_review


ENGINE_VERSION = "resq-agent-rules-v1"
DISCLAIMER = (
    "Academic decision-support prototype. Agent outputs are explainable rules, "
    "not validated emergency guidance or a trained predictive model. Imported "
    "alerts are unverified. A human operator must assess the original bulletin "
    "and local conditions. No incident, resource assignment, notification, or "
    "dispatch is created by this assessment."
)


def assess_alert(alert: dict[str, Any], as_of: datetime | None = None) -> dict[str, Any]:
    """Execute each agent independently and return a traceable assessment snapshot."""
    evidence = evaluate_evidence(alert)
    hazard = evaluate_hazard_signal(alert)
    recency = evaluate_recency(alert, as_of=as_of)
    location = evaluate_location(alert)
    coordinator = coordinate_review(alert, evidence, hazard, recency, location)

    summary = (
        f"{str(alert.get('hazard_type') or 'Unknown').replace('_', ' ').title()} alert "
        f"from {str(alert.get('source') or 'unknown').upper()}: "
        f"{coordinator['review_priority'].replace('_', ' ')}. "
        "Human verification is required."
    )

    return {
        "engine_version": ENGINE_VERSION,
        "assessment_status": "completed",
        "review_priority": coordinator["review_priority"],
        "human_review_required": True,
        "summary": summary,
        "agents": {
            "evidence_quality": evidence,
            "hazard_signal": hazard,
            "event_recency": recency,
            "location_evidence": location,
            "review_coordinator": coordinator,
        },
        "disclaimer": DISCLAIMER,
        "generated_at": (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
    }
