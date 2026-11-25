"""
Read-only adapters for public disaster alert feeds.

The adapters normalize provider payloads into one internal shape. They do not
create incidents or trigger response actions. All external data is untrusted
and must be reviewed by an operator before it influences a response.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
GDACS_FEED_URL = (
    "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
    "?eventlist=EQ;TC;FL;VO;DR;WF&alertlevel=green;orange;red"
)
REQUEST_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 6 * 1024 * 1024
USER_AGENT = "ResQ-Command-Academic-Prototype/0.2"


class FeedFetchError(RuntimeError):
    """Raised when a provider cannot be fetched or its response is unusable."""


@dataclass(frozen=True)
class NormalizedAlert:
    source: str
    source_event_id: str
    event_type: str
    hazard_type: str
    title: str
    description: str | None
    location: str | None
    country: str | None
    alert_level: str | None
    alert_score: float | None
    severity_value: float | None
    severity_unit: str | None
    severity_text: str | None
    latitude: float | None
    longitude: float | None
    depth_km: float | None
    event_at: str | None
    source_updated_at: str | None
    source_url: str | None
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary suitable for the repository layer."""
        return asdict(self)


def _download_json(url: str) -> dict[str, Any]:
    """Fetch JSON from a fixed provider URL with a timeout and response cap."""
    request = Request(
        url,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise FeedFetchError(f"Provider request failed: {type(exc).__name__}") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise FeedFetchError("Provider response exceeded the 6 MiB safety limit")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedFetchError("Provider returned invalid UTF-8 JSON") from exc

    if not isinstance(payload, dict):
        raise FeedFetchError("Provider response must be a JSON object")
    return payload


def _to_iso_datetime(value: Any) -> str | None:
    """Normalize ISO-8601 strings and Unix timestamps to UTC ISO-8601."""
    if value is None or value == "":
        return None

    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            seconds = float(value)
            if not math.isfinite(seconds):
                return None
            if abs(seconds) > 100_000_000_000:
                seconds /= 1000
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(timezone.utc)
        else:
            return None
    except (OverflowError, OSError, TypeError, ValueError):
        return None
    return parsed.isoformat()


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalise_alert_level(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower()


def _point_coordinates(geometry: Any) -> tuple[float | None, float | None, float | None]:
    """Read Point coordinates only; do not invent a centroid for polygons."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None, None, None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None, None

    longitude = _safe_float(coordinates[0])
    latitude = _safe_float(coordinates[1])
    depth = _safe_float(coordinates[2]) if len(coordinates) > 2 else None
    if longitude is None or latitude is None:
        return None, None, depth
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None, None, depth
    return latitude, longitude, depth


def _feature_list(payload: dict[str, Any], provider: str) -> list[dict[str, Any]]:
    features = payload.get("features")
    if not isinstance(features, list):
        raise FeedFetchError(f"{provider} response does not contain a GeoJSON features list")
    return [feature for feature in features if isinstance(feature, dict)]


def parse_usgs_geojson(payload: dict[str, Any]) -> list[NormalizedAlert]:
    """Convert a USGS GeoJSON FeatureCollection into normalized earthquake alerts."""
    if payload.get("type") != "FeatureCollection":
        raise FeedFetchError("USGS response is not a GeoJSON FeatureCollection")

    alerts: list[NormalizedAlert] = []
    for feature in _feature_list(payload, "USGS"):
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue

        event_id = feature.get("id") or properties.get("code")
        if not isinstance(event_id, (str, int)) or not str(event_id).strip():
            continue

        magnitude = _safe_float(properties.get("mag"))
        place = properties.get("place")
        place = place.strip() if isinstance(place, str) and place.strip() else None
        title = properties.get("title")
        if not isinstance(title, str) or not title.strip():
            title = f"Earthquake M{magnitude:g} - {place}" if magnitude is not None and place else (
                place or f"USGS earthquake {event_id}"
            )

        latitude, longitude, depth = _point_coordinates(feature.get("geometry"))
        if magnitude is None:
            severity_text = None
        else:
            severity_text = f"Magnitude {magnitude:g}"

        alerts.append(
            NormalizedAlert(
                source="usgs",
                source_event_id=str(event_id),
                event_type="earthquake",
                hazard_type="earthquake",
                title=title[:300],
                description=place,
                location=place,
                country=None,
                alert_level=_normalise_alert_level(properties.get("alert")),
                alert_score=None,
                severity_value=magnitude,
                severity_unit="magnitude" if magnitude is not None else None,
                severity_text=severity_text,
                latitude=latitude,
                longitude=longitude,
                depth_km=depth,
                event_at=_to_iso_datetime(properties.get("time")),
                source_updated_at=_to_iso_datetime(properties.get("updated")),
                source_url=properties.get("url") if isinstance(properties.get("url"), str) else None,
                raw_data=feature,
            )
        )
    return alerts


def _gdacs_hazard_type(event_type: str) -> str:
    return {
        "EQ": "earthquake",
        "TC": "cyclone",
        "FL": "flood",
        "VO": "volcano",
        "DR": "drought",
        "WF": "wildfire",
    }.get(event_type.upper(), "other")


def parse_gdacs_geojson(payload: dict[str, Any]) -> list[NormalizedAlert]:
    """Convert GDACS multi-hazard GeoJSON features into normalized alerts."""
    alerts: list[NormalizedAlert] = []
    for feature in _feature_list(payload, "GDACS"):
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue

        event_type = properties.get("eventtype") or properties.get("event_type")
        event_id = properties.get("eventid") or properties.get("event_id") or feature.get("id")
        if event_type is None or event_id is None:
            continue

        event_type = str(event_type).upper()
        source_event_id = f"{event_type}:{event_id}"
        title_value = properties.get("name") or properties.get("title")
        title = str(title_value).strip() if title_value else f"{event_type} event {event_id}"

        country_value = properties.get("country")
        if not country_value:
            affected = properties.get("affectedcountries")
            if isinstance(affected, list) and affected and isinstance(affected[0], dict):
                country_value = affected[0].get("countryname")
        country = str(country_value).strip() if country_value else None

        severity_data = properties.get("severitydata")
        if not isinstance(severity_data, dict):
            severity_data = {}
        severity_value = _safe_float(
            severity_data.get("severity", properties.get("severity"))
        )
        severity_unit_value = severity_data.get(
            "severityunit", severity_data.get("severityunitname")
        )
        severity_unit = str(severity_unit_value) if severity_unit_value else None
        severity_text_value = severity_data.get(
            "severitytext", properties.get("severitytext")
        )
        severity_text = str(severity_text_value) if severity_text_value else None

        url_data = properties.get("url")
        source_url = None
        if isinstance(url_data, dict):
            source_url = url_data.get("report") or url_data.get("details")
        elif isinstance(url_data, str):
            source_url = url_data
        source_url = source_url or properties.get("reporturl") or properties.get("url_report")
        if not isinstance(source_url, str):
            source_url = None

        latitude, longitude, _ = _point_coordinates(feature.get("geometry"))
        location_value = properties.get("location") or country
        location = str(location_value).strip() if location_value else None
        description_value = properties.get("description")
        description = str(description_value).strip() if description_value else severity_text

        alerts.append(
            NormalizedAlert(
                source="gdacs",
                source_event_id=source_event_id,
                event_type=event_type,
                hazard_type=_gdacs_hazard_type(event_type),
                title=title[:300],
                description=description[:2000] if description else None,
                location=location,
                country=country,
                alert_level=_normalise_alert_level(properties.get("alertlevel")),
                alert_score=_safe_float(properties.get("alertscore")),
                severity_value=severity_value,
                severity_unit=severity_unit,
                severity_text=severity_text,
                latitude=latitude,
                longitude=longitude,
                depth_km=None,
                event_at=_to_iso_datetime(properties.get("fromdate")),
                source_updated_at=_to_iso_datetime(
                    properties.get("datemodified") or properties.get("todate")
                ),
                source_url=source_url,
                raw_data=feature,
            )
        )
    return alerts


def fetch_alerts(source: str) -> list[NormalizedAlert]:
    """Fetch and normalize one configured provider. No arbitrary URLs are accepted."""
    if source == "gdacs":
        return parse_gdacs_geojson(_download_json(GDACS_FEED_URL))
    if source == "usgs":
        return parse_usgs_geojson(_download_json(USGS_FEED_URL))
    raise ValueError(f"Unsupported alert source: {source}")
