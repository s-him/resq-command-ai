"""Unit tests for the explainable specialist-agent pipeline."""

from datetime import datetime, timezone

from app.agents.evidence_agent import evaluate_evidence
from app.agents.hazard_agent import evaluate_hazard_signal
from app.agents.location_agent import evaluate_location
from app.agents.recency_agent import evaluate_recency
from app.agents.review_coordinator import coordinate_review
from app.assessment_orchestrator import assess_alert


BASE_ALERT = {
    "source": "gdacs",
    "source_event_id": "FL:101",
    "event_type": "FL",
    "hazard_type": "flood",
    "title": "Flood alert",
    "description": "Test alert",
    "location": "Example district",
    "country": "Exampleland",
    "alert_level": "orange",
    "alert_score": 1.2,
    "severity_value": 3.1,
    "severity_unit": "m",
    "latitude": 26.9,
    "longitude": 75.8,
    "event_at": "2026-11-25T10:00:00+00:00",
    "source_url": "https://example.test/alert",
}


def test_evidence_agent_reports_completeness_not_truth():
    result = evaluate_evidence(BASE_ALERT)
    assert result["completeness_score"] == 100
    assert result["completeness_grade"] == "high_completeness"
    assert "not a confidence" in result["interpretation"].lower()


def test_evidence_agent_lists_missing_fields():
    alert = {**BASE_ALERT, "latitude": None, "longitude": None, "event_at": None}
    result = evaluate_evidence(alert)
    assert result["completeness_score"] == 55
    assert "coordinates" in result["missing_evidence"]
    assert "event_timestamp" in result["missing_evidence"]


def test_gdacs_red_signal_maps_only_to_provider_level():
    result = evaluate_hazard_signal({**BASE_ALERT, "alert_level": "red"})
    assert result["signal"] == "red_provider_alert"
    assert result["provider_alert_level"] == "red"
    assert "locally validated" in result["limitations"][1]


def test_gdacs_orange_signal_is_preserved():
    result = evaluate_hazard_signal(BASE_ALERT)
    assert result["signal"] == "orange_provider_alert"
    assert result["severity_value"] == 3.1


def test_usgs_magnitude_is_not_converted_to_universal_severity():
    result = evaluate_hazard_signal({
        **BASE_ALERT,
        "source": "usgs",
        "hazard_type": "earthquake",
        "severity_value": 6.4,
        "severity_unit": "magnitude",
        "depth_km": 12.0,
    })
    assert result["signal"] == "earthquake_magnitude_reported"
    assert result["magnitude"] == 6.4
    assert "No universal risk grade" in result["limitations"][0]


def test_recency_agent_buckets_event_age():
    now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    result = evaluate_recency({**BASE_ALERT, "event_at": "2026-11-25T10:00:00Z"}, as_of=now)
    assert result["event_age_hours"] == 2.0
    assert result["recency_band"] == "within_last_six_hours"


def test_recency_agent_flags_future_timestamps():
    now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    result = evaluate_recency({**BASE_ALERT, "event_at": "2026-11-25T13:00:00Z"}, as_of=now)
    assert result["recency_band"] == "future_timestamp"
    assert result["future_timestamp"] is True


def test_recency_agent_handles_missing_time():
    result = evaluate_recency({**BASE_ALERT, "event_at": None})
    assert result["status"] == "insufficient_data"
    assert result["recency_band"] == "unknown"


def test_location_agent_does_not_guess_population_impact():
    result = evaluate_location({**BASE_ALERT, "latitude": None, "longitude": None})
    assert result["location_status"] == "text_location_only"
    assert result["population_exposure"] == "unknown"


def test_review_coordinator_uses_gdacs_provider_level():
    evidence = evaluate_evidence(BASE_ALERT)
    hazard = evaluate_hazard_signal(BASE_ALERT)
    recency = evaluate_recency(BASE_ALERT, as_of=datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc))
    location = evaluate_location(BASE_ALERT)

    result = coordinate_review(BASE_ALERT, evidence, hazard, recency, location)

    assert result["review_priority"] == "priority_review"
    assert result["human_review_required"] is True


def test_review_coordinator_requires_interpretation_for_usgs():
    alert = {
        **BASE_ALERT,
        "source": "usgs",
        "hazard_type": "earthquake",
        "alert_level": None,
        "severity_value": 6.4,
        "severity_unit": "magnitude",
    }
    result = coordinate_review(
        alert,
        evaluate_evidence(alert),
        evaluate_hazard_signal(alert),
        evaluate_recency(alert),
        evaluate_location(alert),
    )
    assert result["review_priority"] == "human_interpretation_required"


def test_orchestrator_returns_five_traceable_agent_results():
    result = assess_alert(BASE_ALERT)
    assert result["assessment_status"] == "completed"
    assert result["review_priority"] == "priority_review"
    assert set(result["agents"]) == {
        "evidence_quality",
        "hazard_signal",
        "event_recency",
        "location_evidence",
        "review_coordinator",
    }
    assert result["human_review_required"] is True
