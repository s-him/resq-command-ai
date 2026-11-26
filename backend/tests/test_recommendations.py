"""Automated tests for POST /api/incidents/{incident_id}/recommendation. Run with: pytest"""

import sqlite3

from app import recommendation_repository

INCIDENT_HIGH = {
    "hazard_type": "building_collapse",
    "description": "Part of an apartment block collapsed; people may be trapped and injured.",
    "location": "Sector 9, Lake View Apartments",
    "reported_at": "2026-11-19T11:15:00+05:30",
    "people_affected": 120,
    "help_needed": ["medical", "shelter"],
}


def add_incident(client, **overrides) -> int:
    response = client.post("/api/incidents", json={**INCIDENT_HIGH, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_resource(client, resource_type, name, quantity, status="available", location="Central Depot", latitude=None, longitude=None):
    response = client.post(
        "/api/resources",
        json={
            "resource_type": resource_type,
            "name": name,
            "quantity_available": quantity,
            "location": location,
            "availability_status": status,
            "latitude": latitude,
            "longitude": longitude,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_missing_incident_returns_404(client):
    response = client.post("/api/incidents/999/recommendation")

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident 999 not found."


def test_recommends_matching_available_resources_and_reports_unavailable(client):
    incident_id = add_incident(client)  # needs medical (ambulance) and shelter
    ambulance = add_resource(client, "ambulance", "City Ambulance Unit A", 3)

    response = client.post(f"/api/incidents/{incident_id}/recommendation")

    assert response.status_code == 201
    body = response.json()
    assert body["incident_id"] == incident_id
    assert body["status"] == "pending"
    assert "created_at" in body
    assert "prototype" in body["disclaimer"].lower()

    # Ambulance matched (120 people -> desired 5, capped at available 3).
    assert len(body["items"]) == 1
    match = body["items"][0]
    assert match["resource_id"] == ambulance["id"]
    assert match["resource_type"] == "ambulance"
    assert match["recommended_quantity"] == 3
    assert match["recommended_quantity"] <= match["available_quantity"]
    assert "ambulance" in match["explanation"]

    # Shelter was not registered, so it is reported as unavailable.
    assert len(body["unavailable_needs"]) == 1
    gap = body["unavailable_needs"][0]
    assert gap["resource_type"] == "shelter"
    assert gap["help_needed"] == ["shelter"]
    assert "No available 'shelter'" in gap["message"]

    # Ambulance matched 3 of 5 estimated -> reported clearly under insufficient_needs.
    assert len(body["insufficient_needs"]) == 1
    shortfall = body["insufficient_needs"][0]
    assert shortfall["resource_type"] == "ambulance"
    assert shortfall["estimated_needed"] == 5
    assert shortfall["available_matched"] == 3
    assert shortfall["shortfall"] == 2
    assert "Insufficient 'ambulance'" in shortfall["message"]


def test_ignores_unavailable_limited_and_zero_quantity_resources(client):
    incident_id = add_incident(client, help_needed=["medical", "shelter"])
    add_resource(client, "ambulance", "Out of Service Ambulance", 4, status="unavailable")
    add_resource(client, "ambulance", "Limited Ambulance", 2, status="limited")
    add_resource(client, "shelter", "Empty Shelter", 0, status="available")

    body = client.post(f"/api/incidents/{incident_id}/recommendation").json()

    assert body["items"] == []
    assert {need["resource_type"] for need in body["unavailable_needs"]} == {
        "ambulance",
        "shelter",
    }


def test_never_recommends_more_than_available_and_groups_shared_types(client):
    # Both food and water map to "supply" -> should only draw from supply stock once.
    incident_id = add_incident(client, people_affected=50, help_needed=["food", "water"])
    add_resource(client, "supply", "Emergency Rations", 20)

    body = client.post(f"/api/incidents/{incident_id}/recommendation").json()

    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["resource_type"] == "supply"
    assert item["for_help_needed"] == ["food", "water"]
    assert item["recommended_quantity"] == 20  # never exceeds available 20


def test_recommends_only_needed_quantity_when_plenty_available(client):
    incident_id = add_incident(client, people_affected=10, help_needed=["medical"])
    add_resource(client, "ambulance", "Central Fleet", 8)

    body = client.post(f"/api/incidents/{incident_id}/recommendation").json()

    assert len(body["items"]) == 1
    assert body["items"][0]["recommended_quantity"] == 1  # ceil(10 / 25) = 1
    assert body["items"][0]["available_quantity"] == 8


def test_generating_recommendation_does_not_reduce_resource_quantities(client):
    incident_id = add_incident(client, people_affected=40, help_needed=["medical", "shelter"])
    add_resource(client, "ambulance", "Unit A", 5)
    add_resource(client, "shelter", "Community Hall", 100)

    before = client.get("/api/resources").json()
    response = client.post(f"/api/incidents/{incident_id}/recommendation")
    assert response.status_code == 201
    after = client.get("/api/resources").json()

    assert before == after


def test_recommendation_is_saved_in_sqlite(client, temp_database):
    incident_id = add_incident(client, people_affected=25, help_needed=["rescue"])
    add_resource(client, "rescue_team", "River Rescue Squad", 2)

    created = client.post(f"/api/incidents/{incident_id}/recommendation").json()

    saved = recommendation_repository.list_recommendations_for_incident(incident_id)
    assert len(saved) == 2  # intake workflow + this request
    assert saved[-1].id == created["id"]
    assert saved[-1].status.value == "pending"

    connection = sqlite3.connect(temp_database)
    row = connection.execute(
        "SELECT id, incident_id, status, created_at FROM recommendations WHERE id = ?",
        (created["id"],),
    ).fetchone()
    connection.close()

    assert row is not None
    assert row[1] == incident_id
    assert row[2] == "pending"
    assert row[3]




def test_recommendation_prefers_nearest_geocoded_resource(client):
    incident_id = add_incident(
        client,
        people_affected=75,
        help_needed=["medical"],
        latitude=28.6139,
        longitude=77.2090,
    )
    nearby = add_resource(
        client,
        "ambulance",
        "Nearby Unit",
        2,
        latitude=28.6140,
        longitude=77.2090,
    )
    farther = add_resource(
        client,
        "ambulance",
        "Farther Unit",
        8,
        latitude=28.7000,
        longitude=77.2090,
    )

    response = client.post(f"/api/incidents/{incident_id}/recommendation")

    assert response.status_code == 201
    items = response.json()["items"]
    assert [item["resource_id"] for item in items] == [nearby["id"], farther["id"]]
    assert items[0]["recommended_quantity"] == 2
    assert items[1]["recommended_quantity"] == 1
    assert items[0]["distance_basis"] == "haversine_straight_line"
    assert items[0]["distance_km"] < items[1]["distance_km"]
    assert "straight-line distance" in items[0]["explanation"].lower()


def test_recommendation_falls_back_to_stock_when_resource_coordinates_missing(client):
    incident_id = add_incident(
        client,
        people_affected=25,
        help_needed=["medical"],
        latitude=28.6139,
        longitude=77.2090,
    )
    low_stock = add_resource(client, "ambulance", "Small Stock", 1)
    high_stock = add_resource(client, "ambulance", "Large Stock", 4)

    response = client.post(f"/api/incidents/{incident_id}/recommendation")

    items = response.json()["items"]
    assert response.status_code == 201
    assert [item["resource_id"] for item in items] == [high_stock["id"]]
    assert items[0]["distance_km"] is None
    assert items[0]["distance_basis"] == "not_available"
