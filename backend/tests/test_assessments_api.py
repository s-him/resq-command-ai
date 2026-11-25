"""API tests for persisted specialist-agent assessments."""

from app import alert_service
from app.alert_sources import NormalizedAlert


def sample_alert():
    return NormalizedAlert(
        source="gdacs",
        source_event_id="FL:assessment-test",
        event_type="FL",
        hazard_type="flood",
        title="Flood assessment test",
        description="A sample alert for the assessment API.",
        location="Example district",
        country="Exampleland",
        alert_level="orange",
        alert_score=1.2,
        severity_value=2.4,
        severity_unit="m",
        severity_text="Water level",
        latitude=26.9,
        longitude=75.8,
        depth_km=None,
        event_at="2026-11-25T10:00:00+00:00",
        source_updated_at="2026-11-25T11:00:00+00:00",
        source_url="https://example.test/assessment",
        raw_data={"id": "FL:assessment-test"},
    )


def test_assessment_requires_existing_alert(client):
    response = client.post("/api/alerts/999/assessments")
    assert response.status_code == 404


def test_assessment_is_saved_and_history_is_readable(client, monkeypatch):
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [sample_alert()],
    )
    client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    alert = client.get("/api/alerts?limit=5").json()["alerts"][0]

    created = client.post(f"/api/alerts/{alert['id']}/assessments")
    assert created.status_code == 201
    body = created.json()
    assert body["alert_id"] == alert["id"]
    assert body["review_priority"] == "priority_review"
    assert body["human_review_required"] is True
    assert len(body["agents"]) == 5

    history = client.get(f"/api/alerts/{alert['id']}/assessments")
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["assessments"][0]["id"] == body["id"]

    fetched = client.get(f"/api/alerts/assessments/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["source_event_id"] == "FL:assessment-test"


def test_assessment_does_not_create_incidents_or_change_alert_review(client, monkeypatch):
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [sample_alert()],
    )
    client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    alert = client.get("/api/alerts?limit=5").json()["alerts"][0]

    result = client.post(f"/api/alerts/{alert['id']}/assessments")
    assert result.status_code == 201

    incidents = client.get("/api/incidents").json()
    refreshed_alert = client.get("/api/alerts?limit=5").json()["alerts"][0]
    assert incidents == []
    assert refreshed_alert["review_status"] == "new"


def test_repeated_assessments_create_history_snapshots(client, monkeypatch):
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [sample_alert()],
    )
    client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    alert = client.get("/api/alerts?limit=5").json()["alerts"][0]

    first = client.post(f"/api/alerts/{alert['id']}/assessments")
    second = client.post(f"/api/alerts/{alert['id']}/assessments")

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert client.get(f"/api/alerts/{alert['id']}/assessments").json()["count"] == 2
