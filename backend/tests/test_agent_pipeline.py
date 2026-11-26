"""Unit and orchestration tests for the five named incident agents."""

from datetime import datetime, timedelta, timezone

from app.agent_orchestrator import run_incident_pipeline
from app.agents.agent_schemas import (
    NotificationNarrative,
    MonitoringSuggestion,
    AllocationNarrative,
    PriorityNarrative,
    SeverityNarrative,
)
from app.llm import LLMClient, LLMInvalidResponse, LLMTimeoutError
from app.schemas import HazardType


def create_incident(client, people=50):
    response = client.post(
        "/api/incidents",
        json={
            "hazard_type": "flood",
            "description": "Rising floodwater reported near the district clinic.",
            "location": "Riverside Ward",
            "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "people_affected": people,
            "help_needed": ["medical", "evacuation"],
            "latitude": 26.9,
            "longitude": 75.8,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


class SuccessfulLLM:
    def complete_json(self, *, system_prompt, user_payload, response_model):
        if response_model is MonitoringSuggestion:
            return MonitoringSuggestion(
                actionable_candidate=True,
                hazard_type=HazardType.FLOOD,
                draft_description="Floodwater has been reported near the clinic.",
                draft_location="Riverside Ward",
                estimated_people_at_risk=50,
                evidence_basis="The supplied operator report states 50 people are affected.",
                rationale="The report describes an active flood and requests evacuation and medical help.",
            )
        if response_model is SeverityNarrative:
            return SeverityNarrative(
                reasoning="The recorded population and immediate-help requests warrant prompt review.",
                caveats=["The score is an unvalidated prototype estimate."],
            )
        if response_model is PriorityNarrative:
            return PriorityNarrative(
                review_reason="The deterministic queue places this incident according to score, people, time and ID.",
                caveats=["The rank is not official emergency guidance."],
            )
        if response_model is AllocationNarrative:
            return AllocationNarrative(
                operational_note="The deterministic matcher has proposed stock-limited options for operator review.",
                cautions=["No team has been dispatched."],
            )
        if response_model is NotificationNarrative:
            return NotificationNarrative(
                summary="Five advisory agents reviewed the reported flood incident.",
                operator_next_step="Verify the report and review the resource proposal before any operational action.",
                cautions=["No inventory was changed."],
            )
        raise AssertionError(f"Unexpected schema: {response_model}")


class FailingLLM:
    def __init__(self, error):
        self.error = error

    def complete_json(self, *, system_prompt, user_payload, response_model):
        raise self.error


def test_all_five_agents_use_validated_llm_suggestions_without_overriding_rules(client):
    create_incident(client)
    resource = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "Central ambulance pool",
            "quantity_available": 3,
            "location": "Central depot",
            "availability_status": "available",
            "latitude": 26.91,
            "longitude": 75.81,
        },
    )
    assert resource.status_code == 201

    incident_id = client.get("/api/incidents").json()[0]["id"]
    run = run_incident_pipeline(incident_id, llm_client=SuccessfulLLM())

    assert [agent["name"] for agent in run["agents"]] == [
        "MonitoringAgent",
        "SeverityAgent",
        "PrioritizationAgent",
        "ResourceAllocationAgent",
        "NotificationAgent",
    ]
    assert all(agent["mode"] == "llm" for agent in run["agents"])
    severity = run["agents"][1]["output"]["authoritative_assessment"]
    assert severity["score"] == client.get(f"/api/incidents/{incident_id}").json()["severity"]["score"]
    dispatch = run["agents"][3]["output"]
    assert dispatch["stock_changed"] is False
    assert dispatch["dispatch_executed"] is False
    assert run["agents"][0]["output"]["incident_created"] is False


def test_every_agent_falls_back_when_llm_returns_invalid_output(client):
    incident = create_incident(client)
    run = run_incident_pipeline(
        incident["id"],
        llm_client=FailingLLM(LLMInvalidResponse("bad JSON")),
    )
    assert [agent["mode"] for agent in run["agents"]] == ["rules"] * 5
    assert "deterministic rules" in run["agents"][0]["rationale"].lower()


def test_every_agent_falls_back_when_llm_times_out(client):
    incident = create_incident(client)
    run = run_incident_pipeline(
        incident["id"],
        llm_client=FailingLLM(LLMTimeoutError("timeout")),
    )
    assert [agent["mode"] for agent in run["agents"]] == ["rules"] * 5


def test_disabled_llm_uses_rules_without_network_access(client):
    incident = create_incident(client)
    disabled = LLMClient(settings_provider=lambda: {
        "enabled": False,
        "base_url": "https://invalid.example.test/v1",
        "api_key": "",
        "model": "unused",
        "timeout_seconds": 1.0,
    })
    run = run_incident_pipeline(incident["id"], llm_client=disabled)
    assert [agent["mode"] for agent in run["agents"]] == ["rules"] * 5


def test_pipeline_reports_missing_incident(client):
    import pytest

    with pytest.raises(LookupError):
        run_incident_pipeline(99999)
