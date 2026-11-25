"""Integration tests for external alert ingestion and operator review."""

from app import alert_service
from app.alert_sources import NormalizedAlert


def sample_alert(source="gdacs", event_id="FL:123", hazard="flood"):
    return NormalizedAlert(
        source=source,
        source_event_id=event_id,
        event_type="FL" if hazard == "flood" else "earthquake",
        hazard_type=hazard,
        title="Flood warning in Exampleland",
        description="Public feed alert for testing.",
        location="Exampleland",
        country="Exampleland",
        alert_level="orange",
        alert_score=1.5,
        severity_value=3.2,
        severity_unit="m",
        severity_text="Water level",
        latitude=26.9,
        longitude=75.8,
        depth_km=None,
        event_at="2026-11-20T10:00:00+00:00",
        source_updated_at="2026-11-20T11:00:00+00:00",
        source_url="https://example.test/alert/123",
        raw_data={"id": event_id},
    )


def test_alerts_empty_before_first_sync(client):
    response = client.get("/api/alerts")

    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["total_count"] == 0


def test_sync_imports_alerts_and_repeat_sync_deduplicates(client, monkeypatch):
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [sample_alert(source=source, event_id="FL:123")],
    )

    first = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    assert first.status_code == 200
    assert first.json()["status"] == "success"
    assert first.json()["created_count"] == 1
    assert first.json()["updated_count"] == 0

    second = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    assert second.status_code == 200
    assert second.json()["created_count"] == 0
    assert second.json()["updated_count"] == 1

    listed = client.get("/api/alerts?source=gdacs&hazard_type=flood").json()
    assert listed["count"] == 1
    assert listed["total_count"] == 1
    assert listed["alerts"][0]["review_status"] == "new"
    assert listed["alerts"][0]["source_event_id"] == "FL:123"


def test_sync_preserves_human_review_when_provider_updates_alert(client, monkeypatch):
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [sample_alert(source=source)],
    )
    client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    alert_id = client.get("/api/alerts").json()["alerts"][0]["id"]

    reviewed = client.post(
        f"/api/alerts/{alert_id}/review",
        json={"status": "reviewed", "note": "Checked against the official bulletin."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "reviewed"

    client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    refreshed = client.get("/api/alerts").json()["alerts"][0]
    assert refreshed["review_status"] == "reviewed"
    assert refreshed["review_note"] == "Checked against the official bulletin."


def test_failed_provider_does_not_cancel_other_provider(client, monkeypatch):
    def fake_fetch(source):
        if source == "gdacs":
            raise RuntimeError("provider temporarily unavailable")
        return []

    monkeypatch.setattr(alert_service.alert_sources, "fetch_alerts", fake_fetch)

    response = client.post(
        "/api/alerts/sync",
        json={"sources": ["gdacs", "usgs"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert [item["status"] for item in response.json()["sources"]] == ["failed", "success"]
    sources = client.get("/api/alerts/sources").json()
    gdacs = next(item for item in sources if item["source"] == "gdacs")
    assert gdacs["last_sync"]["status"] == "failed"
    assert "RuntimeError" in gdacs["last_sync"]["error_message"]


def test_review_requires_existing_alert(client):
    response = client.post(
        "/api/alerts/999/review",
        json={"status": "dismissed"},
    )

    assert response.status_code == 404


def test_invalid_sync_source_is_rejected(client):
    response = client.post("/api/alerts/sync", json={"sources": ["made-up-feed"]})
    assert response.status_code == 422
