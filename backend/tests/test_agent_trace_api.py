"""API tests for immutable incident agent-trace storage."""

from datetime import datetime, timedelta, timezone


def test_agent_run_is_saved_and_trace_is_readable_without_dispatch(client):
    incident = client.post(
        "/api/incidents",
        json={
            "hazard_type": "earthquake",
            "description": "Shaking and minor structural damage reported in Ward 4.",
            "location": "Ward 4",
            "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            "people_affected": 18,
            "help_needed": ["rescue", "medical"],
        },
    )
    assert incident.status_code == 201
    incident_id = incident.json()["id"]

    resource = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "Ward 4 ambulance",
            "quantity_available": 2,
            "location": "Ward 4 depot",
            "availability_status": "available",
        },
    )
    assert resource.status_code == 201

    history_before = client.get(f"/api/incidents/{incident_id}/history").json()

    run = client.post(f"/api/incidents/{incident_id}/agent-runs")
    assert run.status_code == 201, run.text
    run_body = run.json()
    assert run_body["incident_id"] == incident_id
    assert len(run_body["agents"]) == 5
    assert run_body["duration_ms"] >= 0
    assert all(agent["mode"] == "rules" for agent in run_body["agents"])
    assert run_body["agents"][3]["output"]["dispatch_executed"] is False

    trace = client.get(f"/api/incidents/{incident_id}/agent-trace")
    assert trace.status_code == 200
    assert trace.json()["count"] == 2  # intake workflow run + this manual run
    assert trace.json()["traces"][0]["id"] == run_body["id"]

    # Running the agents is analysis only: no recommendation, plan or stock change.
    history = client.get(f"/api/incidents/{incident_id}/history")
    assert history.status_code == 200
    assert history.json() == history_before
    assert client.get("/api/resources").json()[0]["quantity_available"] == 2
    assert client.get("/api/response-plans").json()["plans"] == []


def test_agent_trace_endpoints_return_not_found_for_unknown_incident(client):
    assert client.get("/api/incidents/99999/agent-trace").status_code == 404
    assert client.post("/api/incidents/99999/agent-runs").status_code == 404


def test_multiple_agent_runs_are_kept_as_separate_snapshots(client):
    incident = client.post(
        "/api/incidents",
        json={
            "hazard_type": "fire",
            "description": "Smoke reported in a residential block near the market.",
            "location": "Market Road",
            "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat(),
            "people_affected": 12,
            "help_needed": ["firefighting", "evacuation"],
        },
    ).json()
    first = client.post(f"/api/incidents/{incident['id']}/agent-runs")
    second = client.post(f"/api/incidents/{incident['id']}/agent-runs")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    history = client.get(f"/api/incidents/{incident['id']}/agent-trace").json()
    assert history["count"] == 3  # intake workflow run + two manual runs
    assert history["traces"][0]["id"] == second.json()["id"]
