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



def test_alert_sources_report_background_sync_configuration(client):
    from app import config

    response = client.get("/api/alerts/sources")

    assert response.status_code == 200
    sources = response.json()
    assert {item["source"] for item in sources} == {"gdacs", "usgs"}
    for item in sources:
        assert item["automatic_sync_enabled"] is config.ALERT_AUTO_SYNC_ENABLED
        if config.ALERT_AUTO_SYNC_ENABLED:
            assert item["configured_sync_interval_seconds"] >= 30
        else:
            assert item["configured_sync_interval_seconds"] is None

def test_review_requires_existing_alert(client):
    response = client.post(
        "/api/alerts/999/review",
        json={"status": "dismissed"},
    )

    assert response.status_code == 404


def test_invalid_sync_source_is_rejected(client):
    response = client.post("/api/alerts/sync", json={"sources": ["made-up-feed"]})
    assert response.status_code == 422


def test_provider_failure_logs_once_exposes_offline_status_and_recovers(
    client, monkeypatch, caplog
):
    import logging

    from app.alert_sources import FeedFetchError

    def unavailable(_source):
        raise FeedFetchError("network unreachable")

    monkeypatch.setattr(alert_service.alert_sources, "fetch_alerts", unavailable)
    with caplog.at_level(logging.WARNING, logger="app.alert_service"):
        first = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
        second = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})

    assert first.status_code == second.status_code == 200
    assert first.json()["sources"][0]["status"] == "failed"
    assert second.json()["sources"][0]["status"] == "failed"
    warnings = [
        record for record in caplog.records
        if record.name == "app.alert_service" and record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert "GDACS feed offline" in warnings[0].message
    assert not warnings[0].exc_info

    source = next(
        item for item in client.get("/api/alerts/sources").json()
        if item["source"] == "gdacs"
    )
    assert source["status"] == "offline"
    assert source["offline_since"]
    assert source["failure_count"] == 2
    assert source["retry_after_seconds"] >= source["configured_sync_interval_seconds"]

    monkeypatch.setattr(alert_service.alert_sources, "fetch_alerts", lambda _source: [])
    recovered = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    assert recovered.status_code == 200
    assert recovered.json()["sources"][0]["status"] == "success"

    source = next(
        item for item in client.get("/api/alerts/sources").json()
        if item["source"] == "gdacs"
    )
    assert source["status"] == "ok"
    assert source["offline_since"] is None
    assert source["last_error"] is None
    assert source["failure_count"] == 0
    assert source["retry_after_seconds"] == source["configured_sync_interval_seconds"]


def test_provider_failure_does_not_raise_and_other_feed_still_succeeds(client, monkeypatch):
    def fetch(source):
        if source == "gdacs":
            raise OSError("offline")
        return []

    monkeypatch.setattr(alert_service.alert_sources, "fetch_alerts", fetch)
    response = client.post(
        "/api/alerts/sync",
        json={"sources": ["gdacs", "usgs"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert [row["status"] for row in response.json()["sources"]] == ["failed", "success"]
    statuses = {
        row["source"]: row["status"]
        for row in client.get("/api/alerts/sources").json()
    }
    assert statuses == {"gdacs": "offline", "usgs": "ok"}
