"""Automated tests for operator decision workflow and incident history. Run with: pytest"""

import sqlite3

from fastapi.testclient import TestClient

from app.main import app

SAMPLE_INCIDENT = {
    "hazard_type": "building_collapse",
    "description": "Part of an apartment block collapsed; people may be trapped and injured.",
    "location": "Sector 9, Lake View Apartments",
    "reported_at": "2026-11-19T11:15:00+05:30",
    "people_affected": 120,
    "help_needed": ["medical", "shelter"],
}

SAMPLE_RESOURCE = {
    "resource_type": "ambulance",
    "name": "City Hospital Ambulance Unit A",
    "quantity_available": 3,
    "location": "Central Depot, Ward 4",
    "availability_status": "available",
}


def setup_incident_and_recommendation(client) -> tuple[int, int]:
    """Create one incident, one ambulance resource, and one pending recommendation."""
    incident_id = client.post("/api/incidents", json=SAMPLE_INCIDENT).json()["id"]
    client.post("/api/resources", json=SAMPLE_RESOURCE)
    rec_id = client.post(f"/api/incidents/{incident_id}/recommendation").json()["id"]
    return incident_id, rec_id


def test_approve_recommendation_with_note(client):
    incident_id, rec_id = setup_incident_and_recommendation(client)

    response = client.post(
        f"/api/recommendations/{rec_id}/decision",
        json={"decision": "approved", "note": "Looks good for prototype review."},
    )

    assert response.status_code == 200
    body = response.json()
    rec = body["recommendation"]
    entry = body["history_entry"]

    assert rec["id"] == rec_id
    assert rec["status"] == "approved"
    assert rec["decision_note"] == "Looks good for prototype review."
    assert rec["decided_at"] is not None

    assert entry["incident_id"] == incident_id
    assert entry["recommendation_id"] == rec_id
    assert entry["action"] == "recommendation_approved"
    assert entry["decision"] == "approved"
    assert entry["note"] == "Looks good for prototype review."
    assert entry["created_at"] is not None


def test_reject_recommendation_without_note(client):
    incident_id, rec_id = setup_incident_and_recommendation(client)

    response = client.post(
        f"/api/recommendations/{rec_id}/decision",
        json={"decision": "rejected"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["status"] == "rejected"
    assert body["recommendation"]["decision_note"] is None
    assert body["history_entry"]["action"] == "recommendation_rejected"
    assert body["history_entry"]["incident_id"] == incident_id


def test_decision_is_visible_on_get_recommendation_and_incident_history(client):
    incident_id, rec_id = setup_incident_and_recommendation(client)
    client.post(
        f"/api/recommendations/{rec_id}/decision",
        json={"decision": "approved", "note": "Verified by operator."},
    )

    fetched = client.get(f"/api/recommendations/{rec_id}").json()
    assert fetched["status"] == "approved"
    assert fetched["decision_note"] == "Verified by operator."
    assert fetched["decided_at"] is not None

    history = client.get(f"/api/incidents/{incident_id}/history").json()
    assert history["incident_id"] == incident_id
    assert len(history["recommendations"]) == 1
    assert history["recommendations"][0]["status"] == "approved"
    assert len(history["action_history"]) == 1
    assert history["action_history"][0]["recommendation_id"] == rec_id
    assert history["action_history"][0]["decision"] == "approved"


def test_approval_does_not_change_resource_quantities(client):
    _, rec_id = setup_incident_and_recommendation(client)
    before = client.get("/api/resources").json()

    response = client.post(
        f"/api/recommendations/{rec_id}/decision",
        json={"decision": "approved", "note": "Prototype approval only."},
    )
    assert response.status_code == 200

    after = client.get("/api/resources").json()
    assert before == after


def test_missing_recommendation_returns_404(client):
    response = client.post(
        "/api/recommendations/999/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Recommendation 999 not found."

    get_response = client.get("/api/recommendations/999")
    assert get_response.status_code == 404


def test_missing_incident_history_returns_404(client):
    response = client.get("/api/incidents/999/history")
    assert response.status_code == 404
    assert response.json()["detail"] == "Incident 999 not found."


def test_invalid_decision_returns_422(client):
    _, rec_id = setup_incident_and_recommendation(client)

    for bad_decision in ["pending", "dispatch", "maybe"]:
        response = client.post(
            f"/api/recommendations/{rec_id}/decision",
            json={"decision": bad_decision},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Validation failed"
        assert response.json()["errors"][0]["field"] == "decision"


def test_cannot_decide_twice_on_same_recommendation(client):
    _, rec_id = setup_incident_and_recommendation(client)
    first = client.post(
        f"/api/recommendations/{rec_id}/decision",
        json={"decision": "approved"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/recommendations/{rec_id}/decision",
        json={"decision": "rejected"},
    )
    assert second.status_code == 409
    assert "already been approved" in second.json()["detail"]


def test_decision_and_history_survive_server_restart(temp_database):
    with TestClient(app) as first_run:
        incident_id, rec_id = setup_incident_and_recommendation(first_run)
        first_run.post(
            f"/api/recommendations/{rec_id}/decision",
            json={"decision": "approved", "note": "Persist across restart."},
        )

    with TestClient(app) as second_run:
        rec = second_run.get(f"/api/recommendations/{rec_id}").json()
        history = second_run.get(f"/api/incidents/{incident_id}/history").json()

    assert rec["status"] == "approved"
    assert rec["decision_note"] == "Persist across restart."
    assert rec["decided_at"] is not None
    assert len(history["action_history"]) == 1
    assert history["action_history"][0]["note"] == "Persist across restart."


def test_old_recommendations_table_is_upgraded_safely(temp_database):
    """Simulate a database created before decision_note/decided_at columns existed."""
    connection = sqlite3.connect(temp_database)
    connection.execute(
        """
        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hazard_type TEXT NOT NULL, description TEXT NOT NULL, location TEXT NOT NULL,
            reported_at TEXT NOT NULL, people_affected INTEGER NOT NULL,
            help_needed TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO incidents
            (id, hazard_type, description, location, reported_at, people_affected,
             help_needed, status, created_at)
        VALUES (1, 'flood', 'Legacy incident for old recommendation test.', 'Ward 1',
                '2026-11-19T07:00:00+00:00', 10, '["medical"]', 'open',
                '2026-11-19T07:05:00+00:00')
        """
    )
    connection.execute(
        """
        CREATE TABLE recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            items TEXT NOT NULL,
            unavailable_needs TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO recommendations
            (incident_id, status, items, unavailable_needs, summary, created_at)
        VALUES (1, 'pending', '[]', '[]', 'Old recommendation', '2026-11-19T08:00:00+00:00')
        """
    )
    connection.commit()
    connection.close()

    with TestClient(app) as client:
        rec = client.get("/api/recommendations/1").json()

    assert rec["id"] == 1
    assert rec["status"] == "pending"
    assert rec["decision_note"] is None
    assert rec["decided_at"] is None
    assert rec["insufficient_needs"] == []

