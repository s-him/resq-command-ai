"""Coordinator agent that summarizes earlier validated agent outputs."""

from time import perf_counter
from typing import Any

from app.agents.agent_result import AgentResult
from app.agents.agent_schemas import CoordinatorNarrative
from app.agents.base import AgentBase


class CoordinatorAgent(AgentBase):
    name = "CoordinatorAgent"

    def run(self, context: dict[str, Any]) -> AgentResult:
        started = perf_counter()
        incident = self.incident_from(context)
        prior = context.get("agent_results") or []
        prior_json = [
            item.model_dump(mode="json") if isinstance(item, AgentResult) else item
            for item in prior
        ]
        narrative, fallback = self.ask_llm(
            response_model=CoordinatorNarrative,
            system_prompt=(
                "Summarize the validated outputs of the five-stage incident review "
                "for a human operator. Do not make new facts, override severity or "
                "priority, allocate stock, create incidents, or authorize dispatch. "
                "State clearly that all findings are advisory and require human review."
            ),
            user_payload={
                "incident_id": incident.id,
                "hazard_type": incident.hazard_type.value,
                "agent_results": prior_json,
            },
        )
        dispatch = next(
            (item.output for item in prior if isinstance(item, AgentResult) and item.name == "DispatchAgent"),
            {},
        )
        priority = next(
            (item.output for item in prior if isinstance(item, AgentResult) and item.name == "PrioritizationAgent"),
            {},
        )
        if narrative is not None:
            summary = narrative.summary
            next_step = narrative.operator_next_step
            cautions = narrative.cautions
        else:
            rank = priority.get("target_incident_rank")
            allocation_count = len(dispatch.get("allocations", []))
            summary = (
                f"Incident #{incident.id} ({incident.hazard_type.value}) was reviewed by "
                f"five advisory agents. Deterministic priority rank: "
                f"{'#' + str(rank) if rank is not None else 'not in the open queue'}. "
                f"{allocation_count} resource allocation suggestion(s) were calculated."
            )
            next_step = (
                "An authorized human operator should verify the report, confirm needs "
                "and resource availability, and use the existing manual approval workflow."
            )
            cautions = [
                "No incident was created or modified by the agent run.",
                "No physical inventory was changed and no team was dispatched.",
                "Severity, priority and resource allocations use prototype deterministic rules.",
            ]
        output = {
            "summary": summary,
            "operator_next_step": next_step,
            "cautions": cautions,
            "agent_count": len(prior),
            "operator_authorization_required": True,
            "dispatch_executed": False,
        }
        return self.finish(
            name=self.name,
            started_at=started,
            mode="llm" if narrative is not None else "rules",
            output=output,
            rationale=fallback or "Coordinator combined the preceding agent results without changing their decisions.",
            confidence=0.9,
        )
