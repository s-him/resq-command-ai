"""Automated tests for POST/GET /api/resources. Run with: pytest"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

VALID_RESOURCE = {
    "resource_type": "ambulance",
    "name": "City Hospital Ambulance Unit A",
    "quantity_available": 3,
    "location": "Central Depot, Ward 4",
    "availability_status": "available",
}


def error_fields(response) -> list[str]:
    """Helper: the list of field names mentioned in a validation error response."""
    return [error["field"] for error in response.json()["errors"]]


# ---------- Creating resources ----------


def test_create_resource_returns_201_with_id(client):
    response = client.post("/api/resources", json=VALID_RESOURCE)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["resource_type"] == "ambulance"
    assert body["name"] == "City Hospital Ambulance Unit A"
    assert body["quantity_available"] == 3
    assert body["location"] == "Central Depot, Ward 4"
    assert body["availability_status"] == "available"
    assert "created_at" in body


@pytest.mark.parametrize(
    "resource_type",
    ["ambulance", "rescue_team", "shelter", "supply", "other"],
)
def test_supported_resource_types_are_accepted(client, resource_type):
    response = client.post(
        "/api/resources",
        json={**VALID_RESOURCE, "resource_type": resource_type},
    )

    assert response.status_code == 201
    assert response.json()["resource_type"] == resource_type


def test_zero_quantity_is_allowed(client):
    response = client.post(
        "/api/resources",
        json={**VALID_RESOURCE, "quantity_available": 0, "availability_status": "unavailable"},
    )

    assert response.status_code == 201
    assert response.json()["quantity_available"] == 0


# ---------- Listing and persistence ----------


def test_list_resources_is_empty_at_start(client):
    response = client.get("/api/resources")

    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_saved_resources_oldest_first(client):
    client.post("/api/resources", json=VALID_RESOURCE)
    client.post(
        "/api/resources",
        json={**VALID_RESOURCE, "resource_type": "rescue_team", "name": "River Rescue Squad"},
    )

    resources = client.get("/api/resources").json()

    assert [item["resource_type"] for item in resources] == ["ambulance", "rescue_team"]


def test_resources_survive_server_restart(temp_database):
    # First "run" of the server: save a resource.
    with TestClient(app) as first_run:
        first_run.post("/api/resources", json=VALID_RESOURCE)

    # Second "run" (startup code runs again) using the same database file.
    with TestClient(app) as second_run:
        resources = second_run.get("/api/resources").json()

    assert len(resources) == 1
    assert resources[0]["name"] == "City Hospital Ambulance Unit A"


# ---------- Validation errors ----------


def test_missing_required_fields_are_reported(client):
    response = client.post("/api/resources", json={"resource_type": "supply"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Validation failed"
    assert set(error_fields(response)) == {
        "name",
        "quantity_available",
        "location",
        "availability_status",
    }


def test_negative_quantity_is_rejected(client):
    response = client.post("/api/resources", json={**VALID_RESOURCE, "quantity_available": -1})

    assert response.status_code == 422
    assert error_fields(response) == ["quantity_available"]


def test_unknown_resource_type_is_rejected(client):
    response = client.post("/api/resources", json={**VALID_RESOURCE, "resource_type": "spaceship"})

    assert response.status_code == 422
    assert error_fields(response) == ["resource_type"]


def test_unknown_availability_status_is_rejected(client):
    response = client.post(
        "/api/resources", json={**VALID_RESOURCE, "availability_status": "maybe"}
    )

    assert response.status_code == 422
    assert error_fields(response) == ["availability_status"]


def test_blank_name_and_location_are_rejected(client):
    response = client.post(
        "/api/resources", json={**VALID_RESOURCE, "name": "   ", "location": "  "}
    )

    assert response.status_code == 422
    assert set(error_fields(response)) == {"name", "location"}


def test_client_cannot_set_id(client):
    response = client.post("/api/resources", json={**VALID_RESOURCE, "id": 99})

    assert response.status_code == 422
    assert error_fields(response) == ["id"]


def test_invalid_resource_is_not_saved(client):
    client.post("/api/resources", json={**VALID_RESOURCE, "quantity_available": -5})

    assert client.get("/api/resources").json() == []

