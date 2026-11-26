"""Automated tests for POST/GET /api/incidents. Run with: pytest"""

from fastapi.testclient import TestClient

from app.main import app

VALID_INCIDENT = {
    "hazard_type": "flood",
    "description": "Water entering ground-floor homes near the river bank.",
    "location": "Ward 12, Riverside Road",
    "reported_at": "2026-11-19T10:30:00+05:30",
    "people_affected": 40,
    "help_needed": ["evacuation", "food"],
}


def error_fields(response) -> list[str]:
    """Helper: the list of field names mentioned in a validation error response."""
    return [error["field"] for error in response.json()["errors"]]


# ---------- Creating incidents ----------


def test_create_incident_returns_id_and_open_status(client):
    response = client.post("/api/incidents", json=VALID_INCIDENT)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["status"] == "open"
    assert body["hazard_type"] == "flood"
    assert body["help_needed"] == ["evacuation", "food"]
    assert "created_at" in body


def test_each_incident_gets_a_new_id(client):
    first = client.post("/api/incidents", json=VALID_INCIDENT).json()
    second = client.post("/api/incidents", json=VALID_INCIDENT).json()

    assert second["id"] == first["id"] + 1


# ---------- Listing incidents ----------


def test_list_is_empty_at_start(client):
    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_saved_incidents(client):
    client.post("/api/incidents", json=VALID_INCIDENT)
    client.post("/api/incidents", json={**VALID_INCIDENT, "hazard_type": "fire"})

    incidents = client.get("/api/incidents").json()

    assert [incident["hazard_type"] for incident in incidents] == ["flood", "fire"]


def test_incidents_survive_server_restart(temp_database):
    # First "run" of the server: save an incident.
    with TestClient(app) as first_run:
        first_run.post("/api/incidents", json=VALID_INCIDENT)

    # Second "run" (startup code runs again) using the same database file.
    with TestClient(app) as second_run:
        incidents = second_run.get("/api/incidents").json()

    assert len(incidents) == 1
    assert incidents[0]["location"] == "Ward 12, Riverside Road"


# ---------- Validation errors ----------


def test_missing_fields_are_reported(client):
    response = client.post("/api/incidents", json={"hazard_type": "flood"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Validation failed"
    assert set(error_fields(response)) == {
        "description",
        "location",
        "reported_at",
        "people_affected",
        "help_needed",
    }


def test_unknown_hazard_type_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "hazard_type": "alien_invasion"})

    assert response.status_code == 422
    assert error_fields(response) == ["hazard_type"]


def test_negative_people_affected_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "people_affected": -5})

    assert response.status_code == 422
    assert error_fields(response) == ["people_affected"]


def test_blank_location_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "location": "   "})

    assert response.status_code == 422
    assert error_fields(response) == ["location"]


def test_bad_date_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "reported_at": "yesterday"})

    assert response.status_code == 422
    assert error_fields(response) == ["reported_at"]


def test_future_date_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "reported_at": "2999-01-01T00:00:00Z"})

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "reported_at cannot be in the future"


def test_empty_help_needed_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "help_needed": []})

    assert response.status_code == 422
    assert error_fields(response) == ["help_needed"]


def test_unknown_help_type_is_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "help_needed": ["rescue", "pizza"]})

    assert response.status_code == 422
    assert error_fields(response) == ["help_needed.1"]


def test_duplicate_help_types_are_rejected(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "help_needed": ["food", "food"]})

    assert response.status_code == 422
    assert error_fields(response) == ["help_needed"]


def test_client_cannot_set_status_or_id(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "status": "closed", "id": 99})

    assert response.status_code == 422
    assert set(error_fields(response)) == {"status", "id"}


def test_invalid_data_is_not_saved(client):
    client.post("/api/incidents", json={**VALID_INCIDENT, "people_affected": -1})

    assert client.get("/api/incidents").json() == []


# ---------- Severity scoring ----------


def test_new_incident_includes_six_factor_severity(client):
    from datetime import datetime, timezone

    payload = {
        **VALID_INCIDENT,
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    severity = client.post("/api/incidents", json=payload).json()["severity"]

    assert severity["score"] == 56  # 18 people + 15 immediate + 8 flood + 15 fresh report
    assert severity["max_score"] == 100
    assert severity["level"] == "High"
    assert severity["explanation"].startswith("Score 56/100 (High):")
    assert [factor["factor"] for factor in severity["factors"]] == [
        "people_affected",
        "immediate_help",
        "hazard_type",
        "hazard_signal",
        "event_recency",
        "vulnerable_population",
    ]
    assert sum(factor["max_points"] for factor in severity["factors"]) == 100
    assert "prototype" in severity["disclaimer"].lower()


def test_optional_hazard_signal_metadata_is_saved(client):
    from datetime import datetime, timezone

    response = client.post(
        "/api/incidents",
        json={
            **VALID_INCIDENT,
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "hazard_magnitude": 6.4,
            "hazard_magnitude_unit": "magnitude",
            "provider_alert_level": "orange",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["hazard_magnitude"] == 6.4
    assert body["hazard_magnitude_unit"] == "magnitude"
    assert body["provider_alert_level"] == "orange"
    assert body["severity"]["factors"][3]["points"] == 10


def test_event_at_is_saved_and_used_for_severity_recency(client):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/incidents",
        json={
            **VALID_INCIDENT,
            "reported_at": now.isoformat(),
            "event_at": (now - timedelta(hours=12)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["event_at"] is not None
    assert body["severity"]["factors"][4]["points"] == 9


def test_future_event_time_is_rejected(client):
    from datetime import datetime, timedelta, timezone

    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/incidents",
        json={**VALID_INCIDENT, "event_at": future},
    )
    assert response.status_code == 422
    assert "event_at cannot be in the future" in response.text


def test_hazard_magnitude_requires_a_unit_and_provider_level_is_validated(client):
    partial = client.post(
        "/api/incidents",
        json={**VALID_INCIDENT, "hazard_magnitude": 6.4},
    )
    invalid_level = client.post(
        "/api/incidents",
        json={**VALID_INCIDENT, "provider_alert_level": "purple"},
    )
    assert partial.status_code == 422
    assert invalid_level.status_code == 422


def test_severity_is_saved_and_listed(client):
    created = client.post("/api/incidents", json=VALID_INCIDENT).json()

    listed = client.get("/api/incidents").json()[0]

    assert listed["severity"] == created["severity"]


def test_client_cannot_send_its_own_severity(client):
    response = client.post("/api/incidents", json={**VALID_INCIDENT, "severity": {"score": 100}})

    assert response.status_code == 422
    assert error_fields(response) == ["severity"]


def test_old_incidents_get_scored_on_startup(temp_database):
    """Simulate a database created before severity scoring existed."""
    import sqlite3

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
        INSERT INTO incidents (hazard_type, description, location, reported_at,
                               people_affected, help_needed, status, created_at)
        VALUES ('fire', 'Old record saved before scoring existed.', 'Sector 4',
                '2026-11-18T09:00:00+05:30', 5, '["food"]', 'open',
                '2026-11-18T03:30:00+00:00')
        """
    )
    connection.commit()
    connection.close()

    # Starting the app upgrades the table and scores the old record.
    with TestClient(app) as client:
        incidents = client.get("/api/incidents").json()

    assert len(incidents) == 1
    assert incidents[0]["location"] == "Sector 4"  # original data kept
    assert incidents[0]["severity"]["score"] == 21  # 8 people + 5 basic needs + 8 fire
    assert incidents[0]["severity"]["level"] == "Low"
    assert incidents[0]["latitude"] is None
    assert incidents[0]["longitude"] is None


# ---------- Optional map coordinates ----------


def test_incident_saves_optional_coordinates(client):
    response = client.post(
        "/api/incidents",
        json={**VALID_INCIDENT, "latitude": 12.9716, "longitude": 77.5946},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["latitude"] == 12.9716
    assert body["longitude"] == 77.5946


def test_incident_rejects_partial_or_out_of_range_coordinates(client):
    partial = client.post("/api/incidents", json={**VALID_INCIDENT, "latitude": 12.97})
    assert partial.status_code == 422

    out_of_range = client.post(
        "/api/incidents",
        json={**VALID_INCIDENT, "latitude": 95.0, "longitude": 77.59},
    )
    assert out_of_range.status_code == 422


def test_get_single_incident_and_404(client):
    created = client.post("/api/incidents", json=VALID_INCIDENT).json()

    fetched = client.get(f"/api/incidents/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]

    missing = client.get("/api/incidents/999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Incident 999 not found."

