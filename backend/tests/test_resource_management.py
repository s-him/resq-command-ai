"""API tests for resource inventory maintenance and audit history."""

from datetime import datetime, timedelta, timezone


def create_resource(client, quantity=3):
    response = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "Central Hospital Ambulance Pool",
            "quantity_available": quantity,
            "location": "Central Medical Depot",
            "availability_status": "available",
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_active_simulation(client):
    resource = create_resource(client, quantity=3)
    incident = client.post(
        "/api/incidents",
        json={
            "hazard_type": "flood",
            "description": "Operator-verified flooding near Central Medical Depot.",
            "location": "Central District",
            "reported_at": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
            "people_affected": 75,
            "help_needed": ["medical"],
            "latitude": 28.6140,
            "longitude": 77.2090,
        },
    )
    assert incident.status_code == 201, incident.text

    recommendation = client.post(
        f"/api/incidents/{incident.json()['id']}/recommendation"
    )
    assert recommendation.status_code == 201, recommendation.text
    assert recommendation.json()["items"][0]["resource_id"] == resource["id"]

    recommendation_id = recommendation.json()["id"]
    approved_recommendation = client.post(
        f"/api/recommendations/{recommendation_id}/decision",
        json={"decision": "approved", "note": "Approved for inventory test."},
    )
    assert approved_recommendation.status_code == 200

    plan = client.post(
        f"/api/incidents/{incident.json()['id']}/response-plans",
        json={"recommendation_id": recommendation_id},
    )
    assert plan.status_code == 201, plan.text

    simulation = client.post(
        f"/api/response-plans/{plan.json()['id']}/decision",
        json={"decision": "approve"},
    )
    assert simulation.status_code == 200, simulation.text
    return resource


def test_resource_registration_is_recorded_in_history(client):
    resource = create_resource(client)
    history = client.get(f"/api/resources/{resource['id']}/history")

    assert history.status_code == 200
    body = history.json()
    assert body["count"] == 1
    assert body["entries"][0]["action"] == "created"
    assert body["entries"][0]["changes"]["quantity_available"] == {
        "from": None,
        "to": 3,
    }


def test_resource_update_changes_fields_and_appends_audit_record(client):
    resource = create_resource(client)

    updated = client.patch(
        f"/api/resources/{resource['id']}",
        json={
            "name": "Central Hospital Ambulance Pool - North",
            "quantity_available": 8,
            "availability_status": "limited",
            "note": "One vehicle is under maintenance.",
        },
    )

    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Central Hospital Ambulance Pool - North"
    assert body["quantity_available"] == 8
    assert body["availability_status"] == "limited"

    history = client.get(f"/api/resources/{resource['id']}/history").json()
    assert history["count"] == 2
    latest = history["entries"][0]
    assert latest["action"] == "updated"
    assert latest["note"] == "One vehicle is under maintenance."
    assert latest["changes"]["quantity_available"] == {"from": 3, "to": 8}
    assert latest["changes"]["availability_status"] == {
        "from": "available",
        "to": "limited",
    }


def test_resource_update_requires_at_least_one_field_and_paired_coordinates(client):
    resource = create_resource(client)

    empty = client.patch(f"/api/resources/{resource['id']}", json={"note": "No changes"})
    partial_coordinates = client.patch(
        f"/api/resources/{resource['id']}",
        json={"latitude": 28.7},
    )
    null_name = client.patch(
        f"/api/resources/{resource['id']}",
        json={"name": None},
    )

    assert empty.status_code == 422
    assert partial_coordinates.status_code == 422
    assert null_name.status_code == 422


def test_resource_coordinates_can_be_cleared_together(client):
    resource = create_resource(client)

    updated = client.patch(
        f"/api/resources/{resource['id']}",
        json={"latitude": None, "longitude": None, "note": "Depot coordinate removed."},
    )

    assert updated.status_code == 200
    assert updated.json()["latitude"] is None
    assert updated.json()["longitude"] is None


def test_active_simulation_reservations_block_unsafe_inventory_changes(client):
    resource = create_active_simulation(client)
    resources = client.get("/api/resources").json()
    current = next(item for item in resources if item["id"] == resource["id"])
    assert current["quantity_available"] == 3
    assert current["simulation_reserved_quantity"] == 2
    assert current["simulation_remaining_quantity"] == 1

    reducing_stock = client.patch(
        f"/api/resources/{resource['id']}",
        json={"quantity_available": 1},
    )
    marking_unavailable = client.patch(
        f"/api/resources/{resource['id']}",
        json={"availability_status": "unavailable"},
    )

    assert reducing_stock.status_code == 409
    assert "2 unit(s) are reserved" in reducing_stock.json()["detail"]
    assert marking_unavailable.status_code == 409
    assert "reserved by active simulations" in marking_unavailable.json()["detail"]

    # Reducing physical quantity exactly to the reserved amount is permitted.
    adjusted = client.patch(
        f"/api/resources/{resource['id']}",
        json={"quantity_available": 2, "note": "One additional unit removed from inventory."},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["quantity_available"] == 2
    assert adjusted.json()["simulation_reserved_quantity"] == 2
    assert adjusted.json()["simulation_remaining_quantity"] == 0


def test_resource_update_history_returns_not_found_for_missing_resource(client):
    response = client.get("/api/resources/999/history")
    updated = client.patch("/api/resources/999", json={"name": "Missing resource"})

    assert response.status_code == 404
    assert updated.status_code == 404
