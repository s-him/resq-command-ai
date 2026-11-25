"""Prioritization agent; the existing score/people/time/ID order is authoritative."""

from time import perf_counter
from typing import Any

from app import prioritization
from app.agents.agent_result import AgentResult
from app.agents.agent_schemas import PriorityNarrative
from app.agents.base import AgentBase
from app.schemas import Incident


class PrioritizationAgent(AgentBase):
    name = "PrioritizationAgent"

    def run(self, context: dict[str, Any]) -> AgentResult:
        started = perf_counter()
        incident = self.incident_from(context)
        values = context.get("open_incidents") or []
        open_incidents = [
            value if isinstance(value, Incident) else Incident.model_validate(value)
            for value in values
        ]
        if not open_incidents and incident.status.value == "open":
            open_incidents = [incident]

        ranked = prioritization.rank_incidents(open_incidents)
        ranking = [
            {
                "incident_id": item.id,
                "rank": item.priority.rank,
                "hazard_type": item.hazard_type.value,
                "location": item.location,
                "severity_score": item.severity.score,
                "people_affected_reported": item.people_affected,
                "explanation": item.priority.explanation,
            }
            for item in ranked
        ]
        target = next((item for item in ranking if item["incident_id"] == incident.id), None)
        narrative, fallback = self.ask_llm(
            response_model=PriorityNarrative,
            system_prompt=(
                "Write a short human-readable interpretation of the supplied "
                "deterministic priority ranking. Do not reorder incidents, change "
                "ranks, invent population exposure, or present this prototype order "
                "as official emergency guidance."
            ),
            user_payload={"authoritative_ranking": ranking, "target_incident_id": incident.id},
        )
        output = {
            "ranking": ranking,
            "target_incident_rank": target["rank"] if target else None,
            "target_rule_explanation": target["explanation"] if target else "Incident is not open.",
            "llm_context": narrative.model_dump(mode="json") if narrative is not None else None,
            "ordering_source": "deterministic_prioritization_rules",
        }
        rationale = (
            narrative.review_reason if narrative is not None
            else fallback or output["target_rule_explanation"]
        )
        return self.finish(
            name=self.name,
            started_at=started,
            mode="llm" if narrative is not None else "rules",
            output=output,
            rationale=rationale,
            confidence=0.9,
        )
