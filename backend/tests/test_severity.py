"""Unit tests for the rule-based severity scoring in app/severity.py. Run with: pytest"""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import HelpType, SeverityLevel
from app.severity import (
    RULES_VERSION,
    calculate_severity,
    level_for_score,
    score_event_recency,
    score_hazard_signal,
    score_people_affected,
    score_vulnerable_population,
)

AS_OF = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)

FOOD = HelpType.FOOD
WATER = HelpType.WATER
RESCUE = HelpType.RESCUE
MEDICAL = HelpType.MEDICAL


@pytest.mark.parametrize(
    "people, expected_points",
    [
        (0, 0),
        (1, 8),
        (9, 8),
        (10, 18),
        (49, 18),
        (50, 25),
        (199, 25),
        (200, 30),
        (999, 30),
        (1000, 35),
        (1_000_000, 35),
    ],
)
def test_people_affected_bands(people, expected_points):
    assert score_people_affected(people).points == expected_points


@pytest.mark.parametrize(
    "score, expected_level",
    [
        (0, SeverityLevel.LOW),
        (24, SeverityLevel.LOW),
        (25, SeverityLevel.MEDIUM),
        (49, SeverityLevel.MEDIUM),
        (50, SeverityLevel.HIGH),
        (74, SeverityLevel.HIGH),
        (75, SeverityLevel.CRITICAL),
        (100, SeverityLevel.CRITICAL),
    ],
)
def test_level_thresholds(score, expected_level):
    assert level_for_score(score) == expected_level


def test_basic_needs_only_scores_five_help_points():
    result = calculate_severity(
        5,
        [FOOD, WATER],
        hazard_type="flood",
        reported_at=AS_OF - timedelta(days=4),
        as_of=AS_OF,
    )

    assert result.factors[1].points == 5
    assert result.score == 21  # 8 (people) + 5 (help) + 8 (flood)
    assert result.level == SeverityLevel.LOW


def test_one_immediate_help_type_scores_15_help_points():
    result = calculate_severity(
        60,
        [MEDICAL, FOOD],
        hazard_type="flood",
        reported_at=AS_OF - timedelta(hours=2),
        as_of=AS_OF,
    )

    assert result.factors[1].points == 15
    assert result.score == 60  # 25 + 15 + 8 + 12 recency
    assert result.level == SeverityLevel.HIGH


def test_two_immediate_help_types_score_20_help_points():
    result = calculate_severity(
        300,
        [RESCUE, MEDICAL],
        hazard_type="earthquake",
        reported_at=AS_OF - timedelta(days=4),
        as_of=AS_OF,
    )

    assert result.factors[1].points == 20
    assert result.score == 60  # 30 + 20 + 10
    assert result.level == SeverityLevel.HIGH


def test_maximum_score_is_100():
    everything_immediate = [RESCUE, MEDICAL, HelpType.EVACUATION, HelpType.FIREFIGHTING]
    result = calculate_severity(
        1_000_000,
        everything_immediate,
        hazard_type="building_collapse",
        reported_at=AS_OF - timedelta(minutes=5),
        provider_alert_level="red",
        description="A school building has collapsed.",
        as_of=AS_OF,
    )

    assert result.score == 100


def test_explanation_lists_each_factor_and_its_points():
    result = calculate_severity(
        60,
        [MEDICAL],
        hazard_type="flood",
        reported_at=AS_OF - timedelta(hours=2),
        as_of=AS_OF,
    )

    assert result.explanation.startswith("Score 60/100 (High):")
    for factor in result.factors:
        assert f"+{factor.points}/{factor.max_points}" in result.explanation
        assert factor.reason in result.explanation



def test_result_is_labelled_as_prototype_estimate():
    result = calculate_severity(5, [FOOD])

    assert "prototype" in result.disclaimer.lower()
    assert "not real emergency guidance" in result.disclaimer.lower()
    assert result.rules_version == RULES_VERSION == "demo-rules-v2"




@pytest.mark.parametrize(
    "level,expected",
    [("green", 4), ("orange", 10), ("red", 15)],
)
def test_provider_alert_levels_map_to_documented_bands(level, expected):
    factor = score_hazard_signal("flood", provider_alert_level=level)
    assert factor.points == expected
    assert factor.max_points == 15


def test_earthquake_magnitude_maps_to_severity_signal():
    moderate = score_hazard_signal("earthquake", 5.6, "magnitude")
    strong = score_hazard_signal("earthquake", 6.8, "magnitude")
    assert moderate.points == 9
    assert strong.points == 12


def test_cyclone_category_and_wind_speed_are_supported():
    category = score_hazard_signal("cyclone", 3, "category")
    wind = score_hazard_signal("cyclone", 115, "knots")
    fractional_category = score_hazard_signal("cyclone", 3.5, "category")
    assert category.points == 12
    assert wind.points == 15
    assert fractional_category.points == 0


@pytest.mark.parametrize(
    "depth,unit,expected",
    [(0.1, "m", 0), (0.3, "m", 4), (60, "cm", 10), (1.2, "m", 15)],
)
def test_flood_water_depth_maps_to_documented_signal_bands(depth, unit, expected):
    factor = score_hazard_signal("flood", depth, unit)
    assert factor.points == expected
    assert factor.max_points == 15
    assert "flood-water depth" in factor.reason


def test_hazard_signal_uses_strongest_supported_signal_without_double_counting():
    factor = score_hazard_signal(
        "earthquake",
        7.2,
        "magnitude",
        provider_alert_level="orange",
    )
    assert factor.points == 15
    assert "strongest supported signal used" in factor.reason


def test_unsupported_magnitude_units_are_not_assigned_invented_points():
    factor = score_hazard_signal("flood", 3.2, "km")
    assert factor.points == 0
    assert "no prototype scoring band" in factor.reason


@pytest.mark.parametrize(
    "age,expected",
    [
        (timedelta(minutes=30), 15),
        (timedelta(hours=3), 12),
        (timedelta(hours=12), 9),
        (timedelta(hours=48), 5),
        (timedelta(days=4), 0),
    ],
)
def test_event_recency_bands(age, expected):
    factor = score_event_recency(AS_OF - age, as_of=AS_OF)
    assert factor.points == expected
    assert factor.max_points == 15


def test_future_or_missing_report_time_is_not_given_recency_points():
    future = score_event_recency(AS_OF + timedelta(minutes=1), as_of=AS_OF)
    missing = score_event_recency(None, as_of=AS_OF)
    assert future.points == 0
    assert "future" in future.reason
    assert missing.points == 0
    assert "missing or invalid" in missing.reason


def test_vulnerable_population_terms_are_case_insensitive():
    factor = score_vulnerable_population(
        "Flooding affects the primary SCHOOL and nearby elderly residents.",
        "Ward 12",
    )
    assert factor.points == 5
    assert "school" in factor.reason
    assert "elderly" in factor.reason


def test_all_six_factors_can_reach_one_hundred_without_double_counting():
    result = calculate_severity(
        1_000_000,
        [HelpType.RESCUE, HelpType.MEDICAL],
        hazard_type="building_collapse",
        reported_at=AS_OF - timedelta(minutes=5),
        hazard_magnitude=7,
        hazard_magnitude_unit="magnitude",
        provider_alert_level="red",
        description="A school has sustained structural damage.",
        as_of=AS_OF,
    )
    assert result.score == 100
    assert result.level == SeverityLevel.CRITICAL
    assert [factor.points for factor in result.factors] == [35, 20, 10, 15, 15, 5]
