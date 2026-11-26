"""Dispatch planning agent; allocations come only from the deterministic stock-safe matcher."""

from time import perf_counter
from typing import Any

from app import recommendations
from app.agents.agent_result import AgentResult
from app.agents.agent_schemas import AllocationNarrative
from app.agents.base import AgentBase
from app.schemas import Resource


class ResourceAllocationAgent(AgentBase):
    name = "ResourceAllocationAgent"

    def run(self, context: dict[str, Any]) -> AgentResult:
        started = perf_counter()
        incident = self.incident_from(context)
        resources = [
            item if isinstance(item, Resource) else Resource.model_validate(item)
            for item in (context.get("available_resources") or [])
        ]
        items, unavailable, insufficient, summary = recommendations.build_recommendation(
            incident, resources
        )
        allocations = [item.model_dump(mode="json") for item in items]
        unavailable_json = [item.model_dump(mode="json") for item in unavailable]
        insufficient_json = [item.model_dump(mode="json") for item in insufficient]
        narrative, fallback = self.ask_llm(
            response_model=AllocationNarrative,
            system_prompt=(
                "Add concise operational context to the supplied resource proposal. "
                "Do not change resource IDs, quantities, availability, distances, or "
                "shortfalls. Do not suggest contacting responders or performing a "
                "real dispatch. The proposal is simulation/planning information only."
            ),
            user_payload={
                "incident": {
                    "id": incident.id,
                    "hazard_type": incident.hazard_type.value,
                    "location": incident.location,
                },
                "rule_based_allocations": allocations,
                "unavailable_needs": unavailable_json,
                "insufficient_needs": insufficient_json,
            },
        )
        output = {
            "summary": summary,
            "allocations": allocations,
            "unavailable_needs": unavailable_json,
            "insufficient_needs": insufficient_json,
            "llm_context": narrative.model_dump(mode="json") if narrative is not None else None,
            "stock_source": "deterministic_available_inventory_and_simulation_remaining",
            "stock_changed": False,
            "dispatch_executed": False,
            "operator_approval_required": True,
        }
        rationale = (
            narrative.operational_note if narrative is not None
            else fallback or "Allocations were calculated with the existing stock- and distance-aware rules."
        )
        return self.finish(
            name=self.name,
            started_at=started,
            mode="llm" if narrative is not None else "rules",
            output=output,
            rationale=rationale,
            confidence=0.88,
        )
