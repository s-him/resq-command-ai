"""Monitoring agent: validates and normalises incoming reports.

Required fields and value ranges are enforced by the IncidentCreate schema
before this agent runs, and the database assigns the incident ID. All model
fields remain unverified suggestions.
"""

from time import perf_counter
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.agents.agent_result import AgentResult
from app.agents.agent_schemas import MonitoringSuggestion
from app.agents.base import AgentBase
from app.schemas import IncidentCreate


class MonitoringAgent(AgentBase):
    name = "MonitoringAgent"

    @staticmethod
    def normalize_report(report: IncidentCreate) -> IncidentCreate:
        """Collapse stray whitespace so equal reports are stored and grouped alike."""
        cleaned = {
            "description": " ".join(report.description.split()),
            "location": " ".join(report.location.split()),
        }
        # Re-validate: collapsing spaces can make a field shorter than its minimum.
        try:
            return IncidentCreate.model_validate({**report.model_dump(), **cleaned})
        except ValidationError as exc:
            # Reported to the client as the usual 422 with a field-level message.
            raise RequestValidationError(
                [{**error, "loc": ("body", *error["loc"])} for error in exc.errors()]
            ) from exc

    def run(self, context: dict[str, Any]) -> AgentResult:
        started = perf_counter()
        incident = self.incident_from(context)
        normalized_alert = context.get("normalized_source_alert")
        rule_draft = {
            "actionable_candidate": incident.status.value == "open",
            "hazard_type": incident.hazard_type.value,
            "draft_description": incident.description,
            "draft_location": incident.location,
            "estimated_people_at_risk": incident.people_affected,
            "evidence_basis": "Existing incident fields supplied or confirmed by an operator.",
            "rationale": (
                "An existing open incident is a candidate for operational review. "
                "Its source report is not independently verified by this agent."
            ),
        }
        suggestion, fallback = self.ask_llm(
            response_model=MonitoringSuggestion,
            system_prompt=(
                "You are an emergency-report triage assistant. Review the supplied "
                "normalized provider alert when present and the linked incident report. "
                "Return a cautious draft classification. Do not claim the event is "
                "verified. Do not infer population counts or coordinates that are absent "
                "from the input. Any estimate must be explicitly marked as based on "
                "supplied evidence. This is a suggestion for a human operator, not a "
                "command to create an incident or dispatch."
            ),
            user_payload={
                "normalized_source_alert": normalized_alert,
                "incident": {
                    "hazard_type": incident.hazard_type.value,
                    "description": incident.description,
                    "location": incident.location,
                    "people_affected_reported": incident.people_affected,
                    "reported_at": incident.reported_at.isoformat(),
                    "event_at": incident.event_at.isoformat() if incident.event_at else None,
                    "latitude": incident.latitude,
                    "longitude": incident.longitude,
                    "status": incident.status.value,
                },
            },
        )
        draft = suggestion.model_dump(mode="json") if suggestion is not None else rule_draft
        output = {
            "candidate_assessment": draft,
            "source_evidence": (
                "normalized_external_alert"
                if normalized_alert
                else "manual_or_operator_entered_report"
            ),
            "linked_alert_id": normalized_alert.get("id") if normalized_alert else None,
            "existing_incident_record": {
                "incident_id": incident.id,
                "hazard_type": incident.hazard_type.value,
                "location": incident.location,
                "people_affected_reported": incident.people_affected,
                "status": incident.status.value,
            },
            "requires_human_confirmation": True,
            "incident_created": False,
            "verified_emergency": False,
        }
        rationale = (
            suggestion.rationale if suggestion is not None
            else fallback or "Monitoring uses the current operator-entered incident as its evidence."
        )
        return self.finish(
            name=self.name,
            started_at=started,
            mode="llm" if suggestion is not None else "rules",
            output=output,
            rationale=rationale,
            confidence=0.72 if suggestion is not None else 0.55,
        )
