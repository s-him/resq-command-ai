"""Tests for GET /api/incidents/priority and app/prioritization.py. Run with: pytest"""

import sqlite3

BASE = {
    "hazard_type": "flood",
    "description": "Test incident for priority ordering.",
    "location": "Test Ward",
    "reported_at": "2026-11-19T10:00:00+05:30",
}


def create(client, people, help_needed, reported_at=None, location="Test Ward"):
    """Helper: create an incident and return its ID."""
    body = {
        **BASE,
        "people_affected": people,
        "help_needed": help_needed,
        "location": location,
        "reported_at": reported_at or BASE["reported_at"],
    }
    response = client.post("/api/incidents", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def priority_ids(client):
    """Helper: the incident IDs in priority order."""
    return [incident["id"] for incident in client.get("/api/incidents/priority").json()["incidents"]]


def set_status(database_path, incident_id, new_status):
    """Helper: change an incident's status directly in the database
    (there is no API endpoint for this yet)."""
    connection = sqlite3.connect(database_path)
    connection.execute("UPDATE incidents SET status = ? WHERE id = ?", (new_status, incident_id))
    connection.commit()
    connection.close()


def test_empty_list(client):
    body = client.get("/api/incidents/priority").json()

    assert body["count"] == 0
    assert body["incidents"] == []
    assert len(body["ranking_rules"]) == 4
    assert "prototype" in body["disclaimer"].lower()


def test_higher_score_comes_first(client):
    low = create(client, 5, ["food"])  # 10 + 10 = 20
    critical = create(client, 300, ["rescue", "medical"])  # 50 + 40 = 90
    high = create(client, 120, ["medical"])  # 40 + 30 = 70

    assert priority_ids(client) == [critical, high, low]


def test_same_score_more_people_first(client):
    # Both score 55 (10-49 people = 25 points, one immediate help type = 30 points)
    fewer = create(client, 12, ["medical"])
    more = create(client, 40, ["rescue"])

    assert priority_ids(client) == [more, fewer]


def test_same_score_and_people_older_report_first(client):
    newer = create(client, 40, ["rescue"], reported_at="2026-11-19T10:30:00+05:30")
    older = create(client, 40, ["rescue"], reported_at="2026-11-19T09:00:00+05:30")

    assert priority_ids(client) == [older, newer]


def test_reported_time_compares_correctly_across_time_zones(client):
    # 10:30 India time = 05:00 UTC, which is EARLIER than 06:00 UTC,
    # even though "10:30" looks later as text.
    utc_six = create(client, 40, ["rescue"], reported_at="2026-11-19T06:00:00+00:00")
    india_1030 = create(client, 40, ["rescue"], reported_at="2026-11-19T10:30:00+05:30")

    assert priority_ids(client) == [india_1030, utc_six]


def test_complete_tie_lower_id_first(client):
    first = create(client, 40, ["rescue"])
    second = create(client, 40, ["rescue"])

    assert priority_ids(client) == [first, second]


def test_people_affected_does_not_beat_a_higher_score(client):
    # 900 people but basic needs only: 50 + 10 = 60
    many_people = create(client, 900, ["food"])
    # 60 people with two immediate help types: 40 + 40 = 80
    fewer_people = create(client, 60, ["rescue", "medical"])

    assert priority_ids(client) == [fewer_people, many_people]


def test_resolved_and_closed_incidents_are_left_out(client, temp_database):
    keep = create(client, 40, ["rescue"])
    resolved = create(client, 300, ["rescue", "medical"])
    closed = create(client, 120, ["medical"])
    set_status(temp_database, resolved, "resolved")
    set_status(temp_database, closed, "closed")

    body = client.get("/api/incidents/priority").json()

    assert [incident["id"] for incident in body["incidents"]] == [keep]
    assert body["count"] == 1
    # The full list still shows every incident and its status.
    statuses = {incident["id"]: incident["status"] for incident in client.get("/api/incidents").json()}
    assert statuses == {keep: "open", resolved: "resolved", closed: "closed"}


def test_each_incident_has_rank_and_explanation(client):
    create(client, 120, ["medical"])  # 70
    create(client, 40, ["rescue"])  # 55
    create(client, 12, ["medical"])  # 55

    incidents = client.get("/api/incidents/priority").json()["incidents"]

    assert [incident["priority"]["rank"] for incident in incidents] == [1, 2, 3]
    assert "higher severity score (70 vs 55)" in incidents[0]["priority"]["explanation"]
    assert "more people affected (40 vs 12)" in incidents[1]["priority"]["explanation"]
    assert "Lowest priority" in incidents[2]["priority"]["explanation"]
    # The full incident, including severity, is still included.
    assert incidents[0]["severity"]["level"] == "High"


def test_explanation_mentions_earlier_report_for_time_tie(client):
    create(client, 40, ["rescue"], reported_at="2026-11-19T10:30:00+05:30")
    create(client, 40, ["rescue"], reported_at="2026-11-19T09:00:00+05:30")

    top = client.get("/api/incidents/priority").json()["incidents"][0]

    assert "reported earlier" in top["priority"]["explanation"]


def test_scores_are_unchanged_by_ranking(client):
    created = client.post(
        "/api/incidents",
        json={**BASE, "people_affected": 120, "help_needed": ["medical"]},
    ).json()

    ranked = client.get("/api/incidents/priority").json()["incidents"][0]

    assert ranked["severity"] == created["severity"]

