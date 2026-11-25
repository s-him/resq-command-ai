"""Small, dependency-free geospatial helpers for prototype resource planning."""

import math


EARTH_MEAN_RADIUS_KM = 6371.0088


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Calculate great-circle distance between two coordinates in kilometres.

    This is a straight-line surface distance. It is not a road route, travel
    time, hazard footprint, or estimate of the affected population.
    """
    coordinates = (latitude_a, longitude_a, latitude_b, longitude_b)
    if not all(math.isfinite(value) for value in coordinates):
        raise ValueError("Coordinates must be finite numbers")
    if not (-90 <= latitude_a <= 90 and -90 <= latitude_b <= 90):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180 <= longitude_a <= 180 and -180 <= longitude_b <= 180):
        raise ValueError("Longitude must be between -180 and 180")

    lat_a, lon_a, lat_b, lon_b = map(
        math.radians,
        (latitude_a, longitude_a, latitude_b, longitude_b),
    )
    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    central_angle = 2 * math.asin(min(1.0, math.sqrt(haversine)))
    return EARTH_MEAN_RADIUS_KM * central_angle
