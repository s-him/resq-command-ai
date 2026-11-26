"""Tests for deterministic affected-area grouping and API ordering."""

from datetime import datetime, timedelta, timezone

from app import incident_repository, prioritization


def create(client, location, people, help_needed, age_hours=5):
    reported_at = (
        datetime.now(timezone.utc) - timedelta(hours=age_hours)
    ).isoformat()
    response = client.post(
        "/api/incidents",
        json={
            "hazard_type": "flood",
            "description": "Reported flooding in the affected neighbourhood.",
            "location": location,
            "reported_at": reported_at,
            "people_affected": people,
            "help_needed": help_needed,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_area_priority_groups_location_labels_case_insensitively(client):
    first = create(client, "North Ward", 20, ["medical"])
    second = create(client, " north ward ", 30, ["rescue"])
    third = create(client, "South Ward", 10, ["food"])

    body = client.get("/api/incidents/areas/priority").json()

    assert body["count"] == 2
    north = next(area for area in body["areas"] if area["area"].casefold() == "north ward")
    assert north["incident_count"] == 2
    assert north["people_affected_reported"] == 50
    assert set(north["incident_ids"]) == {first, second}
    assert north["top_incident_id"] == second
    assert body["areas"][0]["area"].casefold() == "north ward"
    assert third not in north["incident_ids"]


def test_area_priority_uses_highest_incident_severity_then_people(client):
    north_one = create(client, "North Ward", 50, ["medical"])
    north_two = create(client, "North Ward", 10, ["food"])
    south = create(client, "South Ward", 50, ["rescue", "medical"])

    areas = client.get("/api/incidents/areas/priority").json()["areas"]

    assert areas[0]["area"] == "South Ward"
    assert areas[0]["top_incident_id"] == south
    assert areas[1]["area"] == "North Ward"
    assert set(areas[1]["incident_ids"]) == {north_one, north_two}


def test_area_priority_excludes_resolved_and_closed_incidents(client):
    keep = create(client, "North Ward", 20, ["medical"])
    resolved = create(client, "South Ward", 1000, ["rescue", "medical"])
    closed = create(client, "East Ward", 1000, ["rescue", "medical"])
    client.patch(f"/api/incidents/{resolved}/status", json={"status": "resolved"})
    client.patch(f"/api/incidents/{closed}/status", json={"status": "resolved"})
    client.patch(f"/api/incidents/{closed}/status", json={"status": "closed"})

    body = client.get("/api/incidents/areas/priority").json()

    assert body["count"] == 1
    assert body["areas"][0]["area"] == "North Ward"
    assert body["areas"][0]["incident_ids"] == [keep]


def test_area_ranking_is_deterministic_for_equal_aggregates(client):
    first = create(client, "Alpha Ward", 12, ["medical"])
    second = create(client, "Beta Ward", 12, ["medical"])
    incidents = incident_repository.list_open_incidents()

    ranked_once = prioritization.rank_areas(incidents)
    ranked_twice = prioritization.rank_areas(incidents)

    assert [item.area for item in ranked_once] == [item.area for item in ranked_twice]
    assert [item.top_incident_id for item in ranked_once] == [first, second]
    assert all(item.rank == index for index, item in enumerate(ranked_once, start=1))


def test_area_endpoint_returns_empty_list_for_no_open_incidents(client):
    body = client.get("/api/incidents/areas/priority").json()
    assert body["count"] == 0
    assert body["areas"] == []
    assert "location text" in body["disclaimer"].lower()
