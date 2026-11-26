"""Integration tests for repeatable synthetic demo scenarios."""

import pytest


@pytest.mark.parametrize("scenario", ["cyclone", "flood", "earthquake"])
def test_demo_scenario_creates_labeled_records_and_is_idempotent(client, scenario):
    first = client.post("/api/demo/simulate", json={"scenario": scenario})

    assert first.status_code == 201
    result = first.json()
    assert result["scenario"] == scenario
    assert result["dispatch_mode"] == "manual"
    assert result["alerts_created"] == 3
    assert result["incidents_created"] == 3
    assert result["resources_created"] == 4
    assert result["agent_runs"] == 3
    assert len(result["incident_ids"]) == 3
    assert len(result["priority_order"]) >= 3
    assert "SIMULATED" in result["disclaimer"]

    alert_rows = client.get("/api/alerts?limit=500").json()["alerts"]
    demo_alerts = [
        alert for alert in alert_rows
        if alert["source_event_id"].startswith(f"RESQ-DEMO-{scenario.upper()}-")
    ]
    assert len(demo_alerts) == 3
    assert all("SIMULATED" in alert["title"] for alert in demo_alerts)

    all_incidents = client.get("/api/incidents").json()
    demo_incidents = [incident for incident in all_incidents if incident["id"] in result["incident_ids"]]
    assert len(demo_incidents) == 3
    assert all("SIMULATED" in incident["description"] for incident in demo_incidents)
    assert all("SIMULATED" in incident["location"] for incident in demo_incidents)

    resource_rows = client.get("/api/resources").json()
    demo_resources = [
        resource for resource in resource_rows
        if resource["name"].startswith(f"SIMULATED · {scenario.upper()} ·")
    ]
    assert len(demo_resources) == 4

    second = client.post("/api/demo/simulate", json={"scenario": scenario})
    assert second.status_code == 201
    rerun = second.json()
    assert rerun["alerts_created"] == 0
    assert rerun["alerts_updated"] == 3
    assert rerun["incidents_created"] == 0
    assert rerun["resources_created"] == 0
    assert rerun["incident_ids"] == result["incident_ids"]
    assert len(client.get("/api/incidents").json()) == 3


def test_demo_auto_mode_runs_agents_and_creates_virtual_dispatch(client):
    settings = client.patch("/api/dispatch/settings", json={"mode": "auto"})

    assert settings.status_code == 200
    assert settings.json()["mode"] == "auto"

    response = client.post("/api/demo/simulate", json={"scenario": "cyclone"})

    assert response.status_code == 201
    result = response.json()
    assert result["dispatch_mode"] == "auto"
    assert result["agent_runs"] == 3
    assert result["dispatched_count"] == 3
    assert all(item["attempted"] and item["dispatched"] for item in result["dispatch_results"])
    assert not any(item["reused"] for item in result["dispatch_results"])

    plans = client.get("/api/response-plans").json()["plans"]
    automatic_plans = [plan for plan in plans if plan["dispatch_mode"] == "auto"]
    assert len(automatic_plans) == 3
    assert all(plan["status"] == "simulated" for plan in automatic_plans)

    rerun = client.post("/api/demo/simulate", json={"scenario": "cyclone"})
    assert rerun.status_code == 201
    rerun_result = rerun.json()
    assert rerun_result["dispatched_count"] == 3
    assert all(item["reused"] and not item["attempted"] for item in rerun_result["dispatch_results"])
    assert "no duplicate dispatch was created" in rerun_result["message"]
    assert len([
        plan for plan in client.get("/api/response-plans").json()["plans"]
        if plan["dispatch_mode"] == "auto"
    ]) == 3


def test_demo_rejects_unknown_scenario_without_creating_records(client):
    response = client.post("/api/demo/simulate", json={"scenario": "wildfire"})

    assert response.status_code == 422
    assert client.get("/api/incidents").json() == []
    assert client.get("/api/resources").json() == []
