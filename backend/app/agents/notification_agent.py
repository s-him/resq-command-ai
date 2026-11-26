"""Notification and logging agent.

Prepares dashboard alerts and summarises the earlier agent outputs for the
operator. It sends nothing outside the application. Every recorded action is
written to the action_log table by database triggers.
"""

from time import perf_counter
from typing import Any

from app.agents.agent_result import AgentResult
from app.agents.agent_schemas import NotificationNarrative
from app.agents.base import AgentBase
from app.schemas import Incident, Recommendation


class NotificationAgent(AgentBase):
    name = "NotificationAgent"

    @staticmethod
    def incident_alert(incident: Incident) -> dict[str, Any]:
        return {
            "alert_type": "high_severity_incident",
            "incident_id": incident.id,
            "level": incident.severity.level.value,
            "message": (
                f"{incident.severity.level.value} {incident.hazard_type.value.replace('_', ' ')} "
                f"incident #{incident.id} at {incident.location}: "
                f"{incident.people_affected} people reported affected "
                f"(score {incident.severity.score}/{incident.severity.max_score})."
            ),
        }

    @classmethod
    def build_active_alerts(
        cls,
        open_incidents: list[Incident],
        latest_recommendations: dict[int, Recommendation],
        pending_plans: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Derive current alerts from stored state, so none can go stale."""
        alerts: list[dict[str, Any]] = []
        ordered = sorted(open_incidents, key=lambda item: (-item.severity.score, item.id))
        for incident in ordered:
            level = incident.severity.level.value
            if level in {"High", "Critical"}:
                alerts.append(cls.incident_alert(incident))
            recommendation = latest_recommendations.get(incident.id)
            if recommendation is None:
                continue
            if recommendation.status.value == "pending":
                alerts.append({
                    "alert_type": "approval_required",
                    "incident_id": incident.id,
                    "level": level,
                    "message": (
                        f"Recommendation #{recommendation.id} for incident #{incident.id} "
                        "is waiting for an operator decision."
                    ),
                })
            gaps = len(recommendation.unavailable_needs) + len(recommendation.insufficient_needs)
            if gaps:
                alerts.append({
                    "alert_type": "resource_shortfall",
                    "incident_id": incident.id,
                    "level": level,
                    "message": (
                        f"Incident #{incident.id} has {gaps} resource need(s) that were not "
                        f"fully covered in recommendation #{recommendation.id}."
                    ),
                })
        for plan in pending_plans:
            alerts.append({
                "alert_type": "plan_approval_required",
                "incident_id": plan["incident_id"],
                "level": None,
                "message": (
                    f"Response plan #{plan['id']} for incident #{plan['incident_id']} "
                    "is waiting for operator approval."
                ),
            })
        return alerts

    def run(self, context: dict[str, Any]) -> AgentResult:
        started = perf_counter()
        incident = self.incident_from(context)
        prior = context.get("agent_results") or []
        prior_json = [
            item.model_dump(mode="json") if isinstance(item, AgentResult) else item
            for item in prior
        ]
        narrative, fallback = self.ask_llm(
            response_model=NotificationNarrative,
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
            (item.output for item in prior if isinstance(item, AgentResult) and item.name == "ResourceAllocationAgent"),
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
            "alert": (
                self.incident_alert(incident)
                if incident.severity.level.value in {"High", "Critical"}
                else None
            ),
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
            rationale=fallback or "Notification agent combined the preceding agent results without changing their decisions.",
            confidence=0.9,
        )
