"""Tests for promoting reviewed external alerts into the incident workflow."""

from datetime import datetime, timedelta, timezone

from app import alert_service
from app.alert_sources import NormalizedAlert


def promotion_alert():
    now = datetime.now(timezone.utc)
    return NormalizedAlert(
        source="gdacs",
        source_event_id="FL:PROMOTION-001",
        event_type="FL",
        hazard_type="flood",
        title="Flood warning in Exampleland",
        description="Provider reports flooding near Example District.",
        location="Example District",
        country="Exampleland",
        alert_level="orange",
        alert_score=1.5,
        severity_value=3.2,
        severity_unit="m",
        severity_text="Water level",
        latitude=26.9,
        longitude=75.8,
        depth_km=None,
        event_at=(now - timedelta(hours=2)).isoformat(),
        source_updated_at=now.isoformat(),
        source_url="https://example.test/alert/promotion-001",
        raw_data={"id": "FL:PROMOTION-001"},
    )


def import_alert(client, monkeypatch, review_status=None):
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [promotion_alert()],
    )
    sync = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    assert sync.status_code == 200

    alert = client.get("/api/alerts?limit=10").json()["alerts"][0]
    if review_status:
        reviewed = client.post(
            f"/api/alerts/{alert['id']}/review",
            json={
                "status": review_status,
                "note": "Operator checked the provider bulletin.",
            },
        )
        assert reviewed.status_code == 200
        alert = reviewed.json()
    return alert


def valid_incident_payload():
    return {
        "hazard_type": "flood",
        "description": "Operator-verified flooding in homes near Example District.",
        "location": "Example District, Exampleland",
        "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "people_affected": 75,
        "help_needed": ["evacuation", "medical"],
        "latitude": 26.9,
        "longitude": 75.8,
    }


def test_unreviewed_alert_cannot_be_promoted(client, monkeypatch):
    alert = import_alert(client, monkeypatch)

    response = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json=valid_incident_payload(),
    )

    assert response.status_code == 409
    assert "Mark the external alert as reviewed" in response.json()["detail"]
    assert client.get("/api/incidents").json() == []


def test_dismissed_alert_cannot_be_promoted(client, monkeypatch):
    alert = import_alert(client, monkeypatch, review_status="dismissed")

    response = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json=valid_incident_payload(),
    )

    assert response.status_code == 409
    assert client.get("/api/incidents").json() == []


def test_reviewed_alert_promotes_to_open_incident_and_is_linked(client, monkeypatch):
    alert = import_alert(client, monkeypatch, review_status="reviewed")

    response = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json=valid_incident_payload(),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    incident = body["incident"]
    linked_alert = body["alert"]

    assert incident["status"] == "open"
    assert incident["hazard_type"] == "flood"
    assert incident["people_affected"] == 75
    assert incident["help_needed"] == ["evacuation", "medical"]
    assert incident["latitude"] == 26.9
    assert incident["longitude"] == 75.8
    from datetime import datetime

    stored_event_at = datetime.fromisoformat(incident["event_at"].replace("Z", "+00:00"))
    imported_event_at = datetime.fromisoformat(alert["event_at"].replace("Z", "+00:00"))
    assert stored_event_at == imported_event_at
    assert incident["hazard_magnitude"] == 3.2
    assert incident["hazard_magnitude_unit"] == "m"
    assert incident["provider_alert_level"] == "orange"
    assert incident["severity"]["factors"][3]["points"] == 15
    assert incident["severity"]["score"] > 0
    assert linked_alert["review_status"] == "reviewed"
    assert linked_alert["linked_incident_id"] == incident["id"]
    assert linked_alert["linked_at"] is not None

    saved_incidents = client.get("/api/incidents").json()
    assert len(saved_incidents) == 1
    assert saved_incidents[0]["id"] == incident["id"]

    priority = client.get("/api/incidents/priority").json()
    assert priority["count"] == 1
    assert priority["incidents"][0]["id"] == incident["id"]


def test_one_external_alert_cannot_create_two_incidents(client, monkeypatch):
    alert = import_alert(client, monkeypatch, review_status="reviewed")
    first = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json=valid_incident_payload(),
    )
    second = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json=valid_incident_payload(),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already linked to incident" in second.json()["detail"]
    assert len(client.get("/api/incidents").json()) == 1


def test_invalid_incident_details_do_not_promote_or_link_alert(client, monkeypatch):
    alert = import_alert(client, monkeypatch, review_status="reviewed")
    invalid = {**valid_incident_payload(), "help_needed": []}

    response = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json=invalid,
    )

    assert response.status_code == 422
    assert client.get("/api/incidents").json() == []
    refreshed = client.get(f"/api/alerts?review_status=reviewed").json()["alerts"][0]
    assert refreshed["linked_incident_id"] is None


def test_promotion_requires_existing_external_alert(client):
    response = client.post(
        "/api/alerts/999/promote",
        json=valid_incident_payload(),
    )

    assert response.status_code == 404
    assert client.get("/api/incidents").json() == []
