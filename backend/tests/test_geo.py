"""Unit tests for straight-line geographic distance helpers."""

import pytest

from app.geo import haversine_km


def test_haversine_same_point_is_zero():
    assert haversine_km(28.6139, 77.2090, 28.6139, 77.2090) == 0


def test_haversine_one_degree_latitude_is_about_111_km():
    distance = haversine_km(0, 0, 1, 0)
    assert distance == pytest.approx(111.195, abs=0.02)


def test_haversine_is_symmetric():
    forward = haversine_km(28.6, 77.2, 19.0, 72.8)
    backward = haversine_km(19.0, 72.8, 28.6, 77.2)
    assert forward == pytest.approx(backward)


@pytest.mark.parametrize(
    "coordinates",
    [
        (91, 0, 0, 0),
        (0, 181, 0, 0),
        (0, 0, -91, 0),
        (0, 0, 0, -181),
        (float("nan"), 0, 0, 0),
    ],
)
def test_haversine_rejects_invalid_coordinates(coordinates):
    with pytest.raises(ValueError):
        haversine_km(*coordinates)
