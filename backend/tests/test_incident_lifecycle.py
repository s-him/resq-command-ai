"""API tests for incident status changes and operator activity timeline."""

from datetime import datetime, timedelta, timezone


def create_incident(client, suffix="LIFECYCLE"):
    response = client.post(
        "/api/incidents",
        json={
            "hazard_type": "flood",
            "description": f"Operator-verified flooding near district {suffix}.",
            "location": f"District {suffix}",
            "reported_at": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
            "people_affected": 45,
            "help_needed": ["evacuation", "medical"],
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_active_simulation(client, incident_id):
    resource = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "Lifecycle Test Ambulance Pool",
            "quantity_available": 3,
            "location": "Lifecycle Depot",
            "availability_status": "available",
            "latitude": 28.6140,
            "longitude": 77.2090,
        },
    )
    assert resource.status_code == 201, resource.text

    recommendation = client.post(
        f"/api/incidents/{incident_id}/recommendation"
    )
    assert recommendation.status_code == 201, recommendation.text
    recommendation_id = recommendation.json()["id"]

    decision = client.post(
        f"/api/recommendations/{recommendation_id}/decision",
        json={"decision": "approved", "note": "Approved for lifecycle test."},
    )
    assert decision.status_code == 200, decision.text

    plan = client.post(
        f"/api/incidents/{incident_id}/response-plans",
        json={"recommendation_id": recommendation_id},
    )
    assert plan.status_code == 201, plan.text

    simulation = client.post(
        f"/api/response-plans/{plan.json()['id']}/decision",
        json={"decision": "approve"},
    )
    assert simulation.status_code == 200, simulation.text
    return plan.json()["id"]


def test_incident_status_transition_and_reopen_are_audited(client):
    incident_id = create_incident(client)

    resolved = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "resolved", "note": "Area inspected; immediate danger reduced."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"

    reopened = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "open", "note": "New reports indicate continuing flooding."},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"

    timeline = client.get(f"/api/incidents/{incident_id}/updates")
    assert timeline.status_code == 200
    body = timeline.json()
    assert body["count"] == 2
    assert body["active_simulation_count"] == 0
    assert [entry["event_type"] for entry in body["updates"]] == [
        "status_changed",
        "status_changed",
    ]
    assert body["updates"][0]["previous_status"] == "open"
    assert body["updates"][0]["new_status"] == "resolved"
    assert body["updates"][0]["note"] == "Area inspected; immediate danger reduced."
    assert body["updates"][1]["previous_status"] == "resolved"
    assert body["updates"][1]["new_status"] == "open"


def test_incident_must_be_resolved_before_closed_and_closed_is_terminal(client):
    incident_id = create_incident(client)

    direct_close = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "closed"},
    )
    assert direct_close.status_code == 409
    assert "Resolve an open incident before closing it" in direct_close.json()["detail"]

    resolved = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200

    closed = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "closed", "note": "All required follow-up has been completed."},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    reopen = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "open", "note": "Attempt to reopen a closed incident."},
    )
    assert reopen.status_code == 409
    assert "cannot be reopened" in reopen.json()["detail"]


def test_active_simulation_blocks_incident_closure_until_completed(client):
    incident_id = create_incident(client, "ACTIVE-SIM")
    plan_id = create_active_simulation(client, incident_id)

    resolved = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200

    blocked = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "closed"},
    )
    assert blocked.status_code == 409
    assert "response simulation(s) are still active" in blocked.json()["detail"]

    # The failed close did not change the incident status or append a false event.
    timeline = client.get(f"/api/incidents/{incident_id}/updates").json()
    assert timeline["count"] == 1
    assert timeline["active_simulation_count"] == 1

    completed = client.post(
        f"/api/response-plans/{plan_id}/complete",
        json={"note": "Simulation finished."},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    closed = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "closed"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"


def test_operator_note_is_recorded_in_operational_timeline(client):
    incident_id = create_incident(client)

    response = client.post(
        f"/api/incidents/{incident_id}/updates",
        json={"note": "Shelter capacity confirmed at the eastern school."},
    )
    assert response.status_code == 201
    assert response.json()["event_type"] == "operator_note"
    assert response.json()["note"] == "Shelter capacity confirmed at the eastern school."

    timeline = client.get(f"/api/incidents/{incident_id}/updates").json()
    assert timeline["count"] == 1
    assert timeline["updates"][0]["event_type"] == "operator_note"


def test_closed_incident_rejects_new_operator_notes(client):
    incident_id = create_incident(client)
    client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "resolved"},
    )
    client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "closed"},
    )

    response = client.post(
        f"/api/incidents/{incident_id}/updates",
        json={"note": "Late note after closure."},
    )
    assert response.status_code == 409
    assert "closed incident cannot receive" in response.json()["detail"]


def test_status_and_operator_note_requests_validate(client):
    incident_id = create_incident(client)
    invalid_status = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "dispatched"},
    )
    same_status = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "open"},
    )
    blank_note = client.post(
        f"/api/incidents/{incident_id}/updates",
        json={"note": "  "},
    )

    assert invalid_status.status_code == 422
    assert same_status.status_code == 409
    assert blank_note.status_code == 422


def test_incident_update_routes_return_not_found(client):
    status_response = client.patch(
        "/api/incidents/999/status",
        json={"status": "resolved"},
    )
    note_response = client.post(
        "/api/incidents/999/updates",
        json={"note": "This incident does not exist."},
    )
    history_response = client.get("/api/incidents/999/updates")

    assert status_response.status_code == 404
    assert note_response.status_code == 404
    assert history_response.status_code == 404
