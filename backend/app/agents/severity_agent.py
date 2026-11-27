"""Severity agent with deterministic scoring authority and optional LLM reasoning."""

from time import perf_counter
from typing import Any

from app.agents.agent_result import AgentResult
from app.agents.agent_schemas import SeverityNarrative
from app.agents.base import AgentBase
from app import severity


class SeverityAgent(AgentBase):
    name = "SeverityAgent"

    def run(self, context: dict[str, Any]) -> AgentResult:
        started = perf_counter()
        incident = self.incident_from(context)
        assessment = severity.calculate_severity(
            incident.people_affected,
            incident.help_needed,
            hazard_type=incident.hazard_type,
            description=incident.description,
            location=incident.location,
            reported_at=incident.event_at or incident.reported_at,
            hazard_magnitude=incident.hazard_magnitude,
            hazard_magnitude_unit=incident.hazard_magnitude_unit,
            provider_alert_level=incident.provider_alert_level,
            vulnerable_groups=incident.vulnerable_groups,
        )
        assessment_json = assessment.model_dump(mode="json")
        narrative, fallback = self.ask_llm(
            response_model=SeverityNarrative,
            system_prompt=(
                "Explain the incident severity context in plain language. Do not "
                "change, recalculate, or invent a severity score. The deterministic "
                "score and factors provided in the input are authoritative. Identify "
                "uncertainties and never describe an unverified report as confirmed."
            ),
            user_payload={
                "hazard_type": incident.hazard_type.value,
                "hazard_magnitude": incident.hazard_magnitude,
                "hazard_magnitude_unit": incident.hazard_magnitude_unit,
                "provider_alert_level": incident.provider_alert_level,
                "description": incident.description,
                "location": incident.location,
                "people_affected_reported": incident.people_affected,
                "help_needed": [item.value for item in incident.help_needed],
                "authoritative_rule_assessment": assessment_json,
            },
        )
        output = {
            "authoritative_assessment": assessment_json,
            "llm_context": narrative.model_dump(mode="json") if narrative is not None else None,
            "score_source": "deterministic_rules",
        }
        rationale = (
            narrative.reasoning if narrative is not None
            else fallback or "Severity score is calculated by the existing deterministic scoring rules."
        )
        return self.finish(
            name=self.name,
            started_at=started,
            mode="llm" if narrative is not None else "rules",
            output=output,
            rationale=rationale,
            confidence=0.85,
        )
