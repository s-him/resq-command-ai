"""API tests for response plan approvals and simulation-only stock reservations."""

from datetime import datetime, timedelta, timezone


def create_incident(client, suffix):
    reported_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    response = client.post(
        "/api/incidents",
        json={
            "hazard_type": "building_collapse",
            "description": f"Structural collapse report for simulation case {suffix}.",
            "location": f"Test District {suffix}",
            "reported_at": reported_at,
            "people_affected": 50,
            "help_needed": ["medical"],
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_approved_recommendation(client, incident_id):
    recommendation = client.post(f"/api/incidents/{incident_id}/recommendation")
    assert recommendation.status_code == 201, recommendation.text
    recommendation_id = recommendation.json()["id"]

    decision = client.post(
        f"/api/recommendations/{recommendation_id}/decision",
        json={"decision": "approved", "note": "Reviewed for simulation."},
    )
    assert decision.status_code == 200, decision.text
    return recommendation_id


def create_ambulance(client, quantity):
    response = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "Central Simulation Ambulance Pool",
            "quantity_available": quantity,
            "location": "Central Depot",
            "availability_status": "available",
            "latitude": 28.6140,
            "longitude": 77.2090,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_response_plan_requires_approved_recommendation(client):
    create_ambulance(client, 3)
    incident_id = create_incident(client, "PENDING")
    recommendation = client.post(f"/api/incidents/{incident_id}/recommendation")
    assert recommendation.status_code == 201

    response = client.post(
        f"/api/incidents/{incident_id}/response-plans",
        json={"recommendation_id": recommendation.json()["id"]},
    )

    assert response.status_code == 409
    assert "Approve the resource recommendation" in response.json()["detail"]


def test_approved_holds_and_simulation_reservations_release_when_completed(client):
    resource = create_ambulance(client, 3)
    incident_one = create_incident(client, "ONE")
    incident_two = create_incident(client, "TWO")

    recommendation_one = client.post(
        f"/api/incidents/{incident_one}/recommendation"
    ).json()
    recommendation_two = client.post(
        f"/api/incidents/{incident_two}/recommendation"
    ).json()
    assert recommendation_one["items"][0]["recommended_quantity"] == 2
    assert recommendation_two["items"][0]["recommended_quantity"] == 2

    approved_one = client.post(
        f"/api/recommendations/{recommendation_one['id']}/decision",
        json={"decision": "approved", "note": "First allocation approved."},
    )
    assert approved_one.status_code == 200

    # The first approval earmarks two of the three units. The stale second
    # recommendation cannot also claim two units while only one remains.
    blocked_approval = client.post(
        f"/api/recommendations/{recommendation_two['id']}/decision",
        json={"decision": "approved"},
    )
    assert blocked_approval.status_code == 409
    assert "1 unit(s) available" in blocked_approval.json()["detail"]
    assert client.get(
        f"/api/recommendations/{recommendation_two['id']}"
    ).json()["status"] == "pending"

    plan_one_response = client.post(
        f"/api/incidents/{incident_one}/response-plans",
        json={"recommendation_id": recommendation_one["id"]},
    )
    assert plan_one_response.status_code == 201
    plan_one = plan_one_response.json()
    assert plan_one["status"] == "pending"
    assert plan_one["items"][0]["resource_id"] == resource["id"]
    assert plan_one["items"][0]["assigned_quantity"] == 2

    simulated_one = client.post(
        f"/api/response-plans/{plan_one['id']}/decision",
        json={"decision": "approve", "note": "Approve simulation for test."},
    )
    assert simulated_one.status_code == 200, simulated_one.text
    assert simulated_one.json()["plan"]["status"] == "simulated"
    assert client.get("/api/resources").json()[0]["quantity_available"] == 3

    # The active plan now accounts for the same two units. A retry still sees
    # only one unreserved unit and leaves the stale recommendation pending.
    blocked_while_active = client.post(
        f"/api/recommendations/{recommendation_two['id']}/decision",
        json={"decision": "approved"},
    )
    assert blocked_while_active.status_code == 409
    assert "1 unit(s) available" in blocked_while_active.json()["detail"]

    completed = client.post(
        f"/api/response-plans/{plan_one['id']}/complete",
        json={"note": "Simulation completed; release reservation."},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert [entry["action"] for entry in completed.json()["actions"]] == [
        "created",
        "simulated",
        "completed",
    ]

    # Completing the first simulation releases its hold; the second
    # recommendation can now be revalidated and approved.
    approved_two = client.post(
        f"/api/recommendations/{recommendation_two['id']}/decision",
        json={"decision": "approved"},
    )
    assert approved_two.status_code == 200
    plan_two = client.post(
        f"/api/incidents/{incident_two}/response-plans",
        json={"recommendation_id": recommendation_two["id"]},
    )
    assert plan_two.status_code == 201
    simulated_two = client.post(
        f"/api/response-plans/{plan_two.json()['id']}/decision",
        json={"decision": "approve"},
    )
    assert simulated_two.status_code == 200
    assert simulated_two.json()["plan"]["status"] == "simulated"


def test_simulation_reservations_reduce_remaining_stock_for_inventory_and_new_recommendations(client):
    resource = create_ambulance(client, 3)
    first_incident = create_incident(client, "RESERVE-STOCK")
    first_recommendation = create_approved_recommendation(client, first_incident)
    first_plan = client.post(
        f"/api/incidents/{first_incident}/response-plans",
        json={"recommendation_id": first_recommendation},
    ).json()

    approved = client.post(
        f"/api/response-plans/{first_plan['id']}/decision",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200

    inventory = client.get("/api/resources").json()[0]
    assert inventory["quantity_available"] == 3
    assert inventory["simulation_reserved_quantity"] == 2
    assert inventory["simulation_remaining_quantity"] == 1

    second_incident = create_incident(client, "NEW-RECOMMENDATION")
    second_recommendation = client.post(
        f"/api/incidents/{second_incident}/recommendation"
    )
    assert second_recommendation.status_code == 201
    item = second_recommendation.json()["items"][0]
    assert item["resource_id"] == resource["id"]
    assert item["available_quantity"] == 1
    assert item["recommended_quantity"] == 1
    assert second_recommendation.json()["insufficient_needs"][0]["shortfall"] == 1


def test_rejecting_plan_does_not_reserve_resources(client):
    create_ambulance(client, 2)
    incident_id = create_incident(client, "REJECT")
    recommendation_id = create_approved_recommendation(client, incident_id)

    created = client.post(
        f"/api/incidents/{incident_id}/response-plans",
        json={"recommendation_id": recommendation_id},
    )
    plan_id = created.json()["id"]

    rejected = client.post(
        f"/api/response-plans/{plan_id}/decision",
        json={"decision": "reject", "note": "Reject this simulated allocation."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["plan"]["status"] == "rejected"
    assert rejected.json()["plan"]["actions"][-1]["action"] == "rejected"
    assert client.get("/api/resources").json()[0]["quantity_available"] == 2


def test_response_plan_cannot_be_decided_twice(client):
    create_ambulance(client, 2)
    incident_id = create_incident(client, "ONCE")
    recommendation_id = create_approved_recommendation(client, incident_id)
    plan = client.post(
        f"/api/incidents/{incident_id}/response-plans",
        json={"recommendation_id": recommendation_id},
    ).json()

    first = client.post(
        f"/api/response-plans/{plan['id']}/decision",
        json={"decision": "reject"},
    )
    second = client.post(
        f"/api/response-plans/{plan['id']}/decision",
        json={"decision": "approve"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
