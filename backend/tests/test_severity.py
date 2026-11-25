"""Unit tests for the rule-based severity scoring in app/severity.py. Run with: pytest"""

import pytest

from app.schemas import HelpType, SeverityLevel
from app.severity import calculate_severity, level_for_score, score_people_affected

FOOD = HelpType.FOOD
WATER = HelpType.WATER
RESCUE = HelpType.RESCUE
MEDICAL = HelpType.MEDICAL


@pytest.mark.parametrize(
    "people, expected_points",
    [
        (0, 0),
        (1, 10),
        (9, 10),
        (10, 25),
        (49, 25),
        (50, 40),
        (199, 40),
        (200, 50),
        (999, 50),
        (1000, 60),
        (1_000_000, 60),
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


def test_basic_needs_only_scores_10_help_points():
    result = calculate_severity(5, [FOOD, WATER])

    assert result.factors[1].points == 10
    assert result.score == 20  # 10 (people) + 10 (help)
    assert result.level == SeverityLevel.LOW


def test_one_immediate_help_type_scores_30_help_points():
    result = calculate_severity(60, [MEDICAL, FOOD])

    assert result.factors[1].points == 30
    assert result.score == 70  # 40 + 30
    assert result.level == SeverityLevel.HIGH


def test_two_immediate_help_types_score_40_help_points():
    result = calculate_severity(300, [RESCUE, MEDICAL])

    assert result.factors[1].points == 40
    assert result.score == 90  # 50 + 40
    assert result.level == SeverityLevel.CRITICAL


def test_maximum_score_is_100():
    everything_immediate = [RESCUE, MEDICAL, HelpType.EVACUATION, HelpType.FIREFIGHTING]
    result = calculate_severity(1_000_000, everything_immediate)

    assert result.score == 100


def test_explanation_lists_each_factor_and_its_points():
    result = calculate_severity(60, [MEDICAL])

    assert result.explanation == (
        "Score 70/100 (High): 60 people affected (+40); immediate help needed: medical (+30)"
    )


def test_result_is_labelled_as_prototype_estimate():
    result = calculate_severity(5, [FOOD])

    assert "prototype" in result.disclaimer.lower()
    assert "not real emergency guidance" in result.disclaimer.lower()
    assert result.rules_version == "demo-rules-v1"

