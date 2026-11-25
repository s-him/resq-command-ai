"""End-to-end test for the complete reviewed-alert to simulated-response workflow."""

from datetime import datetime, timedelta, timezone

from app import alert_service
from app.alert_sources import NormalizedAlert


def _demo_flood_alert():
    now = datetime.now(timezone.utc)
    return NormalizedAlert(
        source="gdacs",
        source_event_id="FL:E2E-WORKFLOW-001",
        event_type="FL",
        hazard_type="flood",
        title="Flood alert for end-to-end workflow",
        description="Provider reports flooding near the Example District river.",
        location="Example District",
        country="Exampleland",
        alert_level="orange",
        alert_score=1.4,
        severity_value=2.8,
        severity_unit="m",
        severity_text="Reported water level",
        latitude=28.6139,
        longitude=77.2090,
        depth_km=None,
        event_at=(now - timedelta(minutes=20)).isoformat(),
        source_updated_at=now.isoformat(),
        source_url="https://example.test/gdacs/e2e-workflow-001",
        raw_data={"eventid": "E2E-WORKFLOW-001"},
    )


def test_full_operator_workflow_from_feed_to_response_simulation(client, monkeypatch):
    """Sync -> assess -> review -> promote -> recommend -> approve -> simulate -> complete."""
    monkeypatch.setattr(
        alert_service.alert_sources,
        "fetch_alerts",
        lambda source: [_demo_flood_alert()] if source == "gdacs" else [],
    )

    sync = client.post("/api/alerts/sync", json={"sources": ["gdacs"]})
    assert sync.status_code == 200, sync.text
    assert sync.json()["created_count"] == 1

    alert = client.get("/api/alerts?source=gdacs&limit=10").json()["alerts"][0]
    assert alert["review_status"] == "new"

    assessment = client.post(f"/api/alerts/{alert['id']}/assessments")
    assert assessment.status_code == 201, assessment.text
    assert assessment.json()["review_priority"] == "priority_review"
    assert assessment.json()["human_review_required"] is True

    review = client.post(
        f"/api/alerts/{alert['id']}/review",
        json={"status": "reviewed", "note": "Reviewed in end-to-end workflow test."},
    )
    assert review.status_code == 200, review.text

    promotion = client.post(
        f"/api/alerts/{alert['id']}/promote",
        json={
            "hazard_type": "flood",
            "description": "Operator verified flooding in homes near Example District.",
            "location": "Example District, Exampleland",
            "reported_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "people_affected": 40,
            "help_needed": ["medical", "rescue"],
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
    )
    assert promotion.status_code == 201, promotion.text
    incident = promotion.json()["incident"]
    incident_id = incident["id"]
    assert promotion.json()["alert"]["linked_incident_id"] == incident_id

    ambulance = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "E2E Ambulance Pool",
            "quantity_available": 3,
            "location": "Example Central Depot",
            "availability_status": "available",
            "latitude": 28.6140,
            "longitude": 77.2091,
        },
    )
    rescue_team = client.post(
        "/api/resources",
        json={
            "resource_type": "rescue_team",
            "name": "E2E Rescue Team Pool",
            "quantity_available": 3,
            "location": "Example Central Depot",
            "availability_status": "available",
            "latitude": 28.6141,
            "longitude": 77.2092,
        },
    )
    assert ambulance.status_code == rescue_team.status_code == 201

    recommendation = client.post(f"/api/incidents/{incident_id}/recommendation")
    assert recommendation.status_code == 201, recommendation.text
    recommendation_body = recommendation.json()
    assert len(recommendation_body["items"]) == 2
    recommendation_id = recommendation_body["id"]

    recommendation_decision = client.post(
        f"/api/recommendations/{recommendation_id}/decision",
        json={"decision": "approved", "note": "Approved for simulation test."},
    )
    assert recommendation_decision.status_code == 200, recommendation_decision.text

    plan_response = client.post(
        f"/api/incidents/{incident_id}/response-plans",
        json={"recommendation_id": recommendation_id},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    assert plan["status"] == "pending"
    assert len(plan["items"]) == 2

    simulated = client.post(
        f"/api/response-plans/{plan['id']}/decision",
        json={"decision": "approve", "note": "Approve simulated allocation."},
    )
    assert simulated.status_code == 200, simulated.text
    assert simulated.json()["plan"]["status"] == "simulated"

    inventory = client.get("/api/resources").json()
    assert all(resource["quantity_available"] == 3 for resource in inventory)
    assert all(resource["simulation_reserved_quantity"] > 0 for resource in inventory)

    completed = client.post(
        f"/api/response-plans/{plan['id']}/complete",
        json={"note": "End-to-end simulation completed."},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    released_inventory = client.get("/api/resources").json()
    assert all(resource["simulation_reserved_quantity"] == 0 for resource in released_inventory)
    assert len(client.get("/api/incidents").json()) == 1
