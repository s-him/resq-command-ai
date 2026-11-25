"""Unit tests for normalizing the public alert provider payloads."""

import pytest

from app.alert_sources import (
    FeedFetchError,
    parse_gdacs_geojson,
    parse_usgs_geojson,
)


def test_parse_usgs_geojson_normalizes_earthquake():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "us7000abcd",
                "properties": {
                    "mag": 5.6,
                    "place": "12 km east of Example City",
                    "time": 1764000000000,
                    "updated": 1764000300000,
                    "url": "https://earthquake.usgs.gov/example",
                    "alert": "green",
                },
                "geometry": {"type": "Point", "coordinates": [77.1, 28.6, 10.2]},
            }
        ],
    }

    alerts = parse_usgs_geojson(payload)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.source == "usgs"
    assert alert.source_event_id == "us7000abcd"
    assert alert.hazard_type == "earthquake"
    assert alert.severity_value == 5.6
    assert alert.latitude == 28.6
    assert alert.longitude == 77.1
    assert alert.depth_km == 10.2
    assert alert.alert_level == "green"
    assert alert.source_url == "https://earthquake.usgs.gov/example"
    assert alert.raw_data["id"] == "us7000abcd"


def test_parse_gdacs_geojson_normalizes_flood_and_keeps_provider_fields():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "FL-123",
                "properties": {
                    "eventtype": "FL",
                    "eventid": 123,
                    "episodeid": 2,
                    "name": "Flood in Exampleland",
                    "alertlevel": "Orange",
                    "alertscore": 1.5,
                    "country": "Exampleland",
                    "fromdate": "2026-11-20T10:00:00Z",
                    "datemodified": "2026-11-20T11:00:00Z",
                    "severitydata": {
                        "severity": 3.2,
                        "severityunit": "m",
                        "severitytext": "Water level",
                    },
                    "url": {"report": "https://www.gdacs.org/report/123"},
                },
                "geometry": {"type": "Point", "coordinates": [75.8, 26.9]},
            }
        ],
    }

    alerts = parse_gdacs_geojson(payload)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.source == "gdacs"
    assert alert.source_event_id == "FL:123"
    assert alert.hazard_type == "flood"
    assert alert.alert_level == "orange"
    assert alert.alert_score == 1.5
    assert alert.severity_value == 3.2
    assert alert.severity_unit == "m"
    assert alert.country == "Exampleland"
    assert alert.latitude == 26.9
    assert alert.longitude == 75.8
    assert alert.source_url == "https://www.gdacs.org/report/123"


def test_gdacs_uses_event_id_not_episode_id_for_deduplication():
    base = {
        "type": "Feature",
        "properties": {"eventtype": "TC", "eventid": 42, "episodeid": 1, "name": "Cyclone"},
        "geometry": None,
    }
    changed_episode = {
        **base,
        "properties": {**base["properties"], "episodeid": 2},
    }

    first = parse_gdacs_geojson({"features": [base]})[0]
    second = parse_gdacs_geojson({"features": [changed_episode]})[0]

    assert first.source_event_id == second.source_event_id == "TC:42"
    assert first.hazard_type == "cyclone"


def test_bad_geojson_payload_is_rejected():
    with pytest.raises(FeedFetchError):
        parse_usgs_geojson({"features": []})

    with pytest.raises(FeedFetchError):
        parse_gdacs_geojson({"not_features": []})


def test_malformed_coordinates_do_not_crash_or_create_fake_location():
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "us-bad-coordinates",
                "properties": {"mag": 2.1, "place": "Unknown"},
                "geometry": {"type": "Point", "coordinates": [999, 95, 1]},
            }
        ],
    }

    alert = parse_usgs_geojson(payload)[0]

    assert alert.latitude is None
    assert alert.longitude is None
