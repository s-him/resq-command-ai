"""Tests for the synopsis workflow: monitoring, alerts, action history and safety."""

from datetime import datetime, timedelta, timezone

import pytest

from app import database, incident_repository, migrations
from app.severity import score_vulnerable_population


def report(**overrides):
    body = {
        "hazard_type": "flood",
        "description": "Rising floodwater reported near the river bank.",
        "location": "Ward 12",
        "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "people_affected": 300,
        "help_needed": ["rescue", "medical"],
    }
    return {**body, **overrides}


def create(client, **overrides):
    response = client.post("/api/incidents", json=report(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def add_team(client, quantity=4):
    response = client.post(
        "/api/resources",
        json={
            "resource_type": "rescue_team",
            "name": "River rescue pool",
            "quantity_available": quantity,
            "location": "Depot",
            "availability_status": "available",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def activity(client, **params):
    return client.get("/api/activity", params=params).json()["entries"]


def types(entries):
    return [entry["alert_type"] for entry in entries]


# Monitoring agent and automatic workflow


def test_monitoring_agent_normalises_whitespace(client):
    incident = create(client, location="  Ward    12  ", description="Water   entering\n homes nearby.")
    assert incident["location"] == "Ward 12"
    assert incident["description"] == "Water entering homes nearby."


def test_report_that_is_too_short_after_normalising_is_rejected(client):
    response = client.post("/api/incidents", json=report(description="a        bc"))
    assert response.status_code == 422
    assert client.get("/api/incidents").json() == []


def test_new_incident_runs_five_agents_and_waits_for_approval(client):
    add_team(client)
    incident = create(client)

    trace = client.get(f"/api/incidents/{incident['id']}/agent-trace").json()
    assert [agent["name"] for agent in trace["traces"][0]["agents"]] == [
        "MonitoringAgent",
        "SeverityAgent",
        "PrioritizationAgent",
        "ResourceAllocationAgent",
        "NotificationAgent",
    ]
    history = client.get(f"/api/incidents/{incident['id']}/history").json()
    assert [item["status"] for item in history["recommendations"]] == ["pending"]
    assert history["action_history"] == []
    assert client.get("/api/response-plans").json()["plans"] == []
    assert client.get("/api/resources").json()[0]["simulation_reserved_quantity"] == 0


def test_workflow_failure_does_not_lose_the_report(client, monkeypatch):
    from app import agent_orchestrator

    def broken(*args, **kwargs):
        raise RuntimeError("agent failure")

    monkeypatch.setattr(agent_orchestrator, "run_incident_pipeline", broken)
    incident = create(client)
    assert client.get(f"/api/incidents/{incident['id']}").status_code == 200


# AUTO mode is opt-in


def test_auto_mode_is_rejected_unless_allowed(client):
    response = client.patch("/api/dispatch/settings", json={"mode": "auto"})
    assert response.status_code == 409
    assert client.get("/api/dispatch/settings").json()["auto_allowed"] is False


def test_saved_auto_setting_has_no_effect_once_disallowed(client, monkeypatch):
    add_team(client, quantity=50)
    monkeypatch.setenv("RESQ_ALLOW_AUTO_DISPATCH", "true")
    assert client.patch("/api/dispatch/settings", json={"mode": "auto"}).status_code == 200
    monkeypatch.delenv("RESQ_ALLOW_AUTO_DISPATCH")

    create(client)

    assert client.get("/api/dispatch/settings").json()["mode"] == "manual"
    assert client.get("/api/response-plans").json()["plans"] == []


# Alerts (GET /api/alerts)


def test_alerts_include_active_alerts_and_recent_activity(client):
    incident = create(client)
    body = client.get("/api/alerts").json()

    mine = [item for item in body["active_alerts"] if item["incident_id"] == incident["id"]]
    assert {item["alert_type"] for item in mine} == {
        "high_severity_incident",
        "approval_required",
        "resource_shortfall",
    }
    assert "incident_reported" in types(body["recent_activity"])


def test_alerts_clear_when_the_incident_is_resolved(client):
    incident = create(client)
    client.patch(f"/api/incidents/{incident['id']}/status", json={"status": "resolved"})
    assert client.get("/api/alerts").json()["active_alerts"] == []


# Action log (FR-6)


def test_activity_log_records_the_full_manual_workflow(client):
    add_team(client, quantity=20)
    incident = create(client, help_needed=["rescue"])
    base = f"/api/incidents/{incident['id']}"
    recommendation = client.get(f"{base}/history").json()["recommendations"][0]
    client.post(f"/api/recommendations/{recommendation['id']}/decision", json={"decision": "approved"})
    plan = client.post(f"{base}/response-plans", json={"recommendation_id": recommendation["id"]}).json()
    client.post(f"/api/response-plans/{plan['id']}/decision", json={"decision": "approve"})
    client.post(f"/api/response-plans/{plan['id']}/complete", json={})
    client.post(f"{base}/updates", json={"note": "Water level falling."})
    client.patch(f"{base}/status", json={"status": "resolved", "note": "Cleared."})

    recorded = types(activity(client, incident_id=incident["id"]))
    for expected in (
        "incident_reported",
        "recommendation_generated",
        "recommendation_approved",
        "response_plan_created",
        "response_plan_simulated",
        "response_plan_completed",
        "incident_operator_note",
        "incident_status_changed",
    ):
        assert recorded.count(expected) == 1, (expected, recorded)
    assert "resource_created" in types(activity(client))


def test_auto_entries_are_not_described_as_operator_decisions(client, monkeypatch):
    monkeypatch.setenv("RESQ_ALLOW_AUTO_DISPATCH", "true")
    add_team(client, quantity=50)
    client.patch("/api/dispatch/settings", json={"mode": "auto"})
    incident = create(client, help_needed=["rescue"])

    entry = next(
        item for item in activity(client, incident_id=incident["id"])
        if item["alert_type"] == "recommendation_approved"
    )
    assert entry["actor"] == "system-auto"
    assert "no human review" in entry["message"]


def test_recall_is_logged_once_and_not_as_completion(client, monkeypatch):
    monkeypatch.setenv("RESQ_ALLOW_AUTO_DISPATCH", "true")
    add_team(client, quantity=50)
    client.patch("/api/dispatch/settings", json={"mode": "auto"})
    create(client, help_needed=["rescue"])
    plan = client.get("/api/response-plans").json()["plans"][0]

    assert client.post(f"/api/response-plans/{plan['id']}/recall", json={}).status_code == 200

    recorded = types(activity(client))
    assert recorded.count("dispatch_recalled") == 1
    assert "response_plan_completed" not in recorded


def test_upgrade_backfills_existing_history(client):
    incident = create(client)
    client.patch(f"/api/incidents/{incident['id']}/status", json={"status": "resolved"})
    expected = sorted(types(activity(client)))

    connection = database.get_connection()
    try:
        triggers = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'trg_action_log_%'"
        ).fetchall()
        for row in triggers:
            connection.execute(f"DROP TRIGGER {row['name']}")
        connection.execute("DROP TABLE action_log")
        connection.execute("DELETE FROM schema_migrations WHERE version = 14")
        assert migrations.run_migrations(connection) == [14]
    finally:
        connection.close()

    assert sorted(types(activity(client))) == expected


def test_external_alert_review_is_logged(client):
    client.post("/api/demo/simulate", json={"scenario": "flood"})

    reviews = [item for item in activity(client) if item["alert_type"] == "external_alert_reviewed"]

    assert len(reviews) == 3


# Synopsis endpoint alias


def test_actions_decision_endpoint_records_a_decision(client):
    incident = create(client)
    recommendation = client.get(f"/api/incidents/{incident['id']}/history").json()["recommendations"][0]
    url = f"/api/actions/{recommendation['id']}/decision"

    assert client.post(url, json={"decision": "rejected"}).status_code == 200
    assert client.post(url, json={"decision": "approved"}).status_code == 409


# Live severity


def test_open_incident_loses_recency_points_as_it_ages(client):
    incident = create(client)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    connection = database.get_connection()
    try:
        connection.execute("UPDATE incidents SET reported_at = ? WHERE id = ?", (old, incident["id"]))
    finally:
        connection.close()

    updated = incident_repository.get_incident_by_id(incident["id"])
    assert updated.severity.score == incident["severity"]["score"] - 15


def test_resolved_incident_keeps_its_score_at_resolution(client):
    incident = create(client)
    client.patch(f"/api/incidents/{incident['id']}/status", json={"status": "resolved"})
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    connection = database.get_connection()
    try:
        connection.execute("UPDATE incidents SET reported_at = ? WHERE id = ?", (old, incident["id"]))
    finally:
        connection.close()

    assert incident_repository.get_incident_by_id(incident["id"]).severity.score == incident["severity"]["score"]


# Vulnerability keywords


@pytest.mark.parametrize(
    "text",
    [
        "No hospitals or schools nearby are affected.",
        "No hospitals nearby.",
        "No children or elderly at risk.",
        "The school is unaffected.",
        "Hospital was not affected.",
        "Area is clear without any schools nearby",
    ],
)
def test_ruled_out_mentions_score_nothing(text):
    assert score_vulnerable_population(text, "Ward 1").points == 0


@pytest.mark.parametrize(
    "text",
    [
        "School flooded.",
        "No power at the hospital.",
        "No children have been rescued yet.",
        "Elderly residents are not safe.",
        "No schools nearby, but a hospital is flooded.",
    ],
)
def test_real_mentions_still_score(text):
    assert score_vulnerable_population(text, "Ward 1").points == 5
