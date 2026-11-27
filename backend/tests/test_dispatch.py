"""Tests for operator-controlled AUTO dispatch simulation and stock safety."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app import auto_dispatch_repository, dispatch_settings_repository, incident_repository
from app import recommendations as recommendation_builder
from app.dispatch_schemas import DispatchMode, DispatchSettingsUpdate
from app import resource_repository


@pytest.fixture(autouse=True)
def allow_auto_dispatch(monkeypatch):
    """AUTO is off by default; these tests exercise it explicitly."""
    monkeypatch.setenv("RESQ_ALLOW_AUTO_DISPATCH", "true")


def set_dispatch_mode(client, *, mode="auto", paused=False, minimum_severity="High"):
    response = client.patch(
        "/api/dispatch/settings",
        json={
            "mode": mode,
            "paused": paused,
            "minimum_severity": minimum_severity,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_ambulance(client, quantity=3, name="AUTO Ambulance Pool"):
    response = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": name,
            "quantity_available": quantity,
            "location": "Central Depot",
            "availability_status": "available",
            "latitude": 28.6140,
            "longitude": 77.2090,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_eligible_incident(client, *, suffix="AUTO", people=200):
    response = client.post(
        "/api/incidents",
        json={
            "hazard_type": "building_collapse",
            "description": f"Operator-verified structural collapse for {suffix}.",
            "location": f"Test Area {suffix}",
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "people_affected": people,
            "help_needed": ["medical"],
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def list_plans(client):
    response = client.get("/api/response-plans")
    assert response.status_code == 200, response.text
    return response.json()["plans"]


def test_dispatch_mode_is_persisted_and_defaults_to_manual(client):
    settings = client.get("/api/dispatch/settings")

    assert settings.status_code == 200
    assert settings.json()["mode"] == "manual"
    assert settings.json()["paused"] is False
    assert settings.json()["minimum_severity"] == "High"

    create_ambulance(client)
    incident = create_eligible_incident(client, suffix="MANUAL")

    assert list_plans(client) == []
    trace = client.get(f"/api/incidents/{incident['id']}/agent-trace").json()
    assert trace["count"] == 1  # advisory intake run only; nothing is dispatched


def test_auto_dispatch_runs_agents_and_creates_deployed_assignment(client):
    settings = set_dispatch_mode(client)
    assert settings["mode"] == "auto"
    create_ambulance(client)
    incident = create_eligible_incident(client, suffix="AUTO")

    plans = list_plans(client)
    assert len(plans) == 1
    plan = plans[0]
    assert plan["status"] == "simulated"
    assert plan["dispatch_mode"] == "auto"
    assert plan["incident_id"] == incident["id"]
    assert plan["items"][0]["deployment_status"] == "deployed"
    assert plan["items"][0]["assigned_incident_id"] == incident["id"]
    assert plan["items"][0]["assigned_quantity"] == 2

    deployments = client.get("/api/dispatch/deployments?status=deployed").json()
    assert deployments["count"] == 1
    assert deployments["deployments"][0]["actor"] == "system-auto"
    assert deployments["deployments"][0]["incident_id"] == incident["id"]

    audit = client.get(f"/api/dispatch/audit?incident_id={incident['id']}").json()
    assert any(event["actor"] == "system-auto" and event["action"] == "auto_dispatched"
               for event in audit["events"])

    trace = client.get(f"/api/incidents/{incident['id']}/agent-trace").json()
    assert trace["count"] == 1
    assert len(trace["traces"][0]["agents"]) == 5

    resource = client.get("/api/resources").json()[0]
    assert resource["quantity_available"] == 3
    assert resource["simulation_reserved_quantity"] == 2
    assert resource["simulation_remaining_quantity"] == 1
    assert resource["deployed_quantity"] == 2


def test_auto_dispatch_respects_critical_only_threshold(client):
    set_dispatch_mode(client, minimum_severity="Critical")
    create_ambulance(client)
    incident = create_eligible_incident(client, suffix="HIGH-ONLY", people=50)

    assert incident["severity"]["level"] == "High"
    assert list_plans(client) == []
    assert client.get(f"/api/incidents/{incident['id']}/agent-trace").json()["count"] == 1


def test_emergency_pause_blocks_auto_dispatch_until_unpaused(client):
    set_dispatch_mode(client, paused=True)
    create_ambulance(client)
    incident = create_eligible_incident(client, suffix="PAUSED")

    assert list_plans(client) == []
    assert client.get(f"/api/incidents/{incident['id']}/agent-trace").json()["count"] == 1

    updated = client.patch("/api/dispatch/settings", json={"paused": False})
    assert updated.status_code == 200
    plans = list_plans(client)
    assert len(plans) == 1
    assert plans[0]["dispatch_mode"] == "auto"


def test_recall_releases_auto_deployment_reservation_and_records_operator_audit(client):
    set_dispatch_mode(client)
    create_ambulance(client)
    incident = create_eligible_incident(client, suffix="RECALL")
    plan = list_plans(client)[0]

    recalled = client.post(
        f"/api/response-plans/{plan['id']}/recall",
        json={"note": "Operator recalled the simulated assignment."},
    )
    assert recalled.status_code == 200, recalled.text
    body = recalled.json()
    assert body["status"] == "completed"
    assert body["items"][0]["deployment_status"] == "recalled"

    resource = client.get("/api/resources").json()[0]
    assert resource["simulation_reserved_quantity"] == 0
    assert resource["simulation_remaining_quantity"] == 3
    assert resource["deployed_quantity"] == 0

    audit = client.get(f"/api/dispatch/audit?incident_id={incident['id']}").json()
    assert any(event["action"] == "recalled" and event["actor"] == "operator"
               for event in audit["events"])


def test_new_stock_retries_only_the_remaining_shortfall(client):
    set_dispatch_mode(client)
    create_ambulance(client, quantity=1, name="Initial Limited Ambulance Pool")
    incident = create_eligible_incident(client, suffix="TOP-UP")

    first_plan = list_plans(client)[0]
    assert first_plan["items"][0]["assigned_quantity"] == 1
    first_audit = client.get(f"/api/dispatch/audit?incident_id={incident['id']}").json()
    assert first_audit["events"][0]["action"] == "partial_shortfall"

    # Adding stock triggers a top-up attempt. The first unit stays deployed,
    # so the retry must assign only one additional unit, not the original two.
    create_ambulance(client, quantity=2, name="New Ambulance Stock")
    plans = list_plans(client)
    assert len(plans) == 2
    second_plan = next(plan for plan in plans if plan["id"] != first_plan["id"])
    assert second_plan["items"][0]["assigned_quantity"] == 1
    assert second_plan["dispatch_mode"] == "auto"

    active = client.get("/api/dispatch/deployments?status=deployed").json()
    assert sum(item["assigned_quantity"] for item in active["deployments"]) == 2
    assert all(item["actor"] == "system-auto" for item in active["deployments"])


def test_shortfall_retry_endpoint_requires_a_recorded_shortfall(client):
    set_dispatch_mode(client)
    create_ambulance(client, quantity=3)
    incident = create_eligible_incident(client, suffix="NO-RETRY")
    plan = list_plans(client)[0]

    response = client.post(f"/api/dispatch/incidents/{incident['id']}/retry")
    assert response.status_code == 409
    assert "No retryable shortfall" in response.json()["detail"]
    assert len(list_plans(client)) == 1



def test_concurrent_auto_dispatch_cannot_reserve_the_same_last_units(client):
    resource = create_ambulance(client, quantity=2, name="Last Two Ambulances")
    first_data = create_eligible_incident(client, suffix="RACE-ONE")
    second_data = create_eligible_incident(client, suffix="RACE-TWO")

    dispatch_settings_repository.update_dispatch_settings(
        DispatchSettingsUpdate(mode=DispatchMode.AUTO)
    )
    resources = resource_repository.list_available_resources()
    incidents = [
        incident_repository.get_incident_by_id(first_data["id"]),
        incident_repository.get_incident_by_id(second_data["id"]),
    ]
    prepared = []
    for incident in incidents:
        items, unavailable, insufficient, summary = recommendation_builder.build_recommendation(
            incident,
            resources,
        )
        assert items[0].recommended_quantity == 2
        prepared.append((incident, items, unavailable, insufficient, summary))

    def attempt(bundle):
        incident, items, unavailable, insufficient, summary = bundle
        return auto_dispatch_repository.create_auto_dispatch(
            incident=incident,
            items=items,
            unavailable_needs=unavailable,
            insufficient_needs=insufficient,
            summary=summary,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt, bundle) for bundle in prepared]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except auto_dispatch_repository.AutoDispatchStockConflict as exc:
                outcomes.append(exc)

    successes = [item for item in outcomes if isinstance(item, dict)]
    conflicts = [item for item in outcomes if isinstance(item, auto_dispatch_repository.AutoDispatchStockConflict)]
    assert len(successes) == 1
    assert len(conflicts) == 1

    deployments = client.get("/api/dispatch/deployments?status=deployed").json()["deployments"]
    assert sum(item["assigned_quantity"] for item in deployments) == 2
    current = next(item for item in client.get("/api/resources").json() if item["id"] == resource["id"])
    assert current["simulation_reserved_quantity"] == 2
    assert current["simulation_remaining_quantity"] == 0
