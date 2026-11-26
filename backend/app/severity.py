"""
Explainable 0-100 severity scoring for the academic disaster-management prototype.

The weights below are demonstration heuristics, not statistically calibrated risk
estimates and not official emergency guidance. Every factor is returned so that
operators can see exactly what contributed to the score.
"""

import re
from datetime import datetime, timezone
from typing import Any

from app.schemas import (
    HazardType,
    HelpType,
    SeverityAssessment,
    SeverityFactor,
    SeverityLevel,
)

RULES_VERSION = "demo-rules-v2"
MAX_SCORE = 100

DISCLAIMER = (
    "Unvalidated prototype estimate for an academic demonstration. "
    "Not real emergency guidance. Hazard weights and provider-signal bands are "
    "illustrative, not calibrated probabilities. A human operator must review it."
)

# Total possible points: 35 + 20 + 10 + 15 + 15 + 5 = 100.
PEOPLE_BANDS = [
    (1000, 35),
    (200, 30),
    (50, 25),
    (10, 18),
    (1, 8),
    (0, 0),
]
PEOPLE_MAX_POINTS = 35

IMMEDIATE_HELP_TYPES = {
    HelpType.RESCUE,
    HelpType.MEDICAL,
    HelpType.EVACUATION,
    HelpType.FIREFIGHTING,
}
POINTS_NO_IMMEDIATE_HELP = 5
POINTS_ONE_IMMEDIATE_HELP = 15
POINTS_MULTIPLE_IMMEDIATE_HELP = 20
HELP_MAX_POINTS = 20

HAZARD_TYPE_POINTS = {
    HazardType.FLOOD: 8,
    HazardType.EARTHQUAKE: 10,
    HazardType.FIRE: 8,
    HazardType.CYCLONE: 10,
    HazardType.LANDSLIDE: 8,
    HazardType.BUILDING_COLLAPSE: 10,
    HazardType.CHEMICAL_SPILL: 9,
    HazardType.OTHER: 3,
}
HAZARD_TYPE_MAX_POINTS = 10
HAZARD_SIGNAL_MAX_POINTS = 15
RECENCY_MAX_POINTS = 15
VULNERABLE_POPULATION_MAX_POINTS = 5

VULNERABLE_TERMS = (
    "hospital",
    "hospitals",
    "school",
    "schools",
    "elderly",
    "older adults",
    "senior citizens",
    "children",
    "child",
    "infant",
    "baby",
    "nursing home",
    "care home",
    "kindergarten",
    "nursery school",
    "pediatric",
)

LEVEL_THRESHOLDS = [
    (75, SeverityLevel.CRITICAL),
    (50, SeverityLevel.HIGH),
    (25, SeverityLevel.MEDIUM),
    (0, SeverityLevel.LOW),
]


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value)).strip().lower()


def _as_utc(value: datetime) -> datetime:
    """Treat timezone-naive report times as UTC for deterministic comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def score_people_affected(people_affected: int) -> SeverityFactor:
    """Factor 1: reported people affected, capped at 35 prototype points."""
    points = 0
    for minimum_people, band_points in PEOPLE_BANDS:
        if people_affected >= minimum_people:
            points = band_points
            break
    noun = "person" if people_affected == 1 else "people"
    return SeverityFactor(
        factor="people_affected",
        points=points,
        max_points=PEOPLE_MAX_POINTS,
        reason=f"{people_affected} {noun} affected (reported estimate)",
    )


def score_immediate_help(help_needed: list[HelpType]) -> SeverityFactor:
    """Factor 2: requests for immediate life-safety assistance."""
    immediate = [
        item.value for item in help_needed
        if item in IMMEDIATE_HELP_TYPES
    ]
    if len(immediate) >= 2:
        points = POINTS_MULTIPLE_IMMEDIATE_HELP
        reason = "multiple immediate help types requested: " + ", ".join(immediate)
    elif len(immediate) == 1:
        points = POINTS_ONE_IMMEDIATE_HELP
        reason = f"immediate help requested: {immediate[0]}"
    else:
        points = POINTS_NO_IMMEDIATE_HELP
        basic = ", ".join(item.value for item in help_needed) or "none recorded"
        reason = f"no immediate life-safety help recorded (requests: {basic})"
    return SeverityFactor(
        factor="immediate_help",
        points=points,
        max_points=HELP_MAX_POINTS,
        reason=reason,
    )


def score_hazard_type(hazard_type: HazardType | str | None) -> SeverityFactor:
    """Factor 3: small, explicit baseline weight by declared hazard category."""
    value = _enum_value(hazard_type)
    try:
        hazard = HazardType(value) if value else HazardType.OTHER
    except ValueError:
        hazard = HazardType.OTHER
    points = HAZARD_TYPE_POINTS[hazard]
    return SeverityFactor(
        factor="hazard_type",
        points=points,
        max_points=HAZARD_TYPE_MAX_POINTS,
        reason=f"declared hazard category: {hazard.value}",
    )


def _earthquake_magnitude_points(value: float) -> int:
    if value < 4.0:
        return 2
    if value < 5.0:
        return 5
    if value < 6.0:
        return 9
    if value < 7.0:
        return 12
    return 15


def _cyclone_signal_points(value: float, unit: str | None) -> tuple[int, str] | None:
    normalized = (unit or "").strip().lower().replace(" ", "")
    if normalized in {"category", "cat", "saffir-simpson", "saffir_simpson"}:
        if not value.is_integer():
            return None
        category = int(value)
        points = {1: 7, 2: 9, 3: 12, 4: 15, 5: 15}.get(category, 0)
        if 1 <= category <= 5:
            return points, f"reported cyclone category {category}"
        return None

    conversions = {
        "km/h": 1.0,
        "kmh": 1.0,
        "kph": 1.0,
        "knots": 1.852,
        "knot": 1.852,
        "kt": 1.852,
        "m/s": 3.6,
        "ms-1": 3.6,
        "mph": 1.60934,
    }
    factor = conversions.get(normalized)
    if factor is None:
        return None
    wind_kmh = value * factor
    if wind_kmh < 119:
        points = 0
    elif wind_kmh < 154:
        points = 7
    elif wind_kmh < 178:
        points = 9
    elif wind_kmh < 209:
        points = 12
    else:
        points = 15
    return points, f"reported wind speed {wind_kmh:.1f} km/h"


def _flood_depth_points(value: float, unit: str | None) -> tuple[int, str] | None:
    """Map a reported flood-water depth to a bounded prototype signal band."""
    normalized = (unit or "").strip().lower().replace(" ", "")
    conversions = {
        "m": 1.0,
        "metre": 1.0,
        "metres": 1.0,
        "meter": 1.0,
        "meters": 1.0,
        "cm": 0.01,
        "centimetre": 0.01,
        "centimeters": 0.01,
        "mm": 0.001,
        "millimetre": 0.001,
        "millimeters": 0.001,
        "ft": 0.3048,
        "feet": 0.3048,
    }
    factor = conversions.get(normalized)
    if factor is None:
        return None
    depth_m = value * factor
    if depth_m < 0:
        return None
    if depth_m < 0.2:
        points = 0
    elif depth_m < 0.5:
        points = 4
    elif depth_m < 1.0:
        points = 10
    else:
        points = 15
    return points, f"reported flood-water depth {depth_m:.2f} m"


def score_hazard_signal(
    hazard_type: HazardType | str | None,
    hazard_magnitude: float | None = None,
    hazard_magnitude_unit: str | None = None,
    provider_alert_level: str | None = None,
) -> SeverityFactor:
    """Factor 4: provider alert level or supported earthquake/cyclone measurement.

    When both a provider alert level and measurement exist, only the strongest
    applicable signal is used. The factor is capped at 15 to avoid double-counting.
    """
    hazard = _enum_value(hazard_type) or HazardType.OTHER.value
    candidates: list[tuple[int, str]] = []
    level = (provider_alert_level or "").strip().lower()
    provider_points = {"red": 15, "orange": 10, "green": 4}.get(level)
    if provider_points is not None:
        candidates.append((provider_points, f"provider alert level reported as {level}"))

    if hazard_magnitude is not None:
        try:
            magnitude = float(hazard_magnitude)
        except (TypeError, ValueError):
            magnitude = -1
        unit = (hazard_magnitude_unit or "").strip().lower()
        if hazard == HazardType.EARTHQUAKE.value and unit in {
            "magnitude", "mag", "mw", "richter", "moment magnitude",
        } and magnitude >= 0:
            points = _earthquake_magnitude_points(magnitude)
            candidates.append((points, f"reported earthquake magnitude {magnitude:g}"))
        elif hazard == HazardType.CYCLONE.value:
            signal = _cyclone_signal_points(magnitude, unit)
            if signal is not None:
                candidates.append(signal)
        elif hazard == HazardType.FLOOD.value:
            signal = _flood_depth_points(magnitude, unit)
            if signal is not None:
                candidates.append(signal)

    if candidates:
        # Highest supported signal wins; provider + measurement are not added together.
        points, reason = max(candidates, key=lambda item: item[0])
        if len(candidates) > 1:
            reason += "; strongest supported signal used (not additive)"
    else:
        if provider_alert_level:
            reason = f"provider alert level '{provider_alert_level}' has no mapped band"
        elif hazard_magnitude is not None:
            reason = (
                f"reported magnitude {hazard_magnitude:g} {hazard_magnitude_unit or ''} "
                "has no prototype scoring band for this hazard"
            )
        else:
            reason = "no provider alert level or supported hazard measurement supplied"
        points = 0

    return SeverityFactor(
        factor="hazard_signal",
        points=min(HAZARD_SIGNAL_MAX_POINTS, points),
        max_points=HAZARD_SIGNAL_MAX_POINTS,
        reason=reason,
    )


def score_event_recency(
    reported_at: datetime | str | None,
    *,
    as_of: datetime | None = None,
) -> SeverityFactor:
    """Factor 5: newer reported event time gets more prototype review points."""
    event_time = _parse_datetime(reported_at)
    if event_time is None:
        return SeverityFactor(
            factor="event_recency",
            points=0,
            max_points=RECENCY_MAX_POINTS,
            reason="event/report timestamp missing or invalid; recency not scored",
        )

    now = _as_utc(as_of or datetime.now(timezone.utc))
    age_hours = (now - event_time).total_seconds() / 3600
    if age_hours < 0:
        points = 0
        reason = "event/report timestamp is in the future; recency not scored"
    elif age_hours < 1:
        points = 15
        reason = f"reported {age_hours * 60:.0f} minute(s) ago"
    elif age_hours <= 6:
        points = 12
        reason = f"reported {age_hours:.1f} hour(s) ago"
    elif age_hours <= 24:
        points = 9
        reason = f"reported {age_hours:.1f} hour(s) ago"
    elif age_hours <= 72:
        points = 5
        reason = f"reported {age_hours / 24:.1f} day(s) ago"
    else:
        points = 0
        reason = f"reported {age_hours / 24:.1f} day(s) ago; outside the 72-hour recency band"

    return SeverityFactor(
        factor="event_recency",
        points=points,
        max_points=RECENCY_MAX_POINTS,
        reason=reason,
    )


def score_vulnerable_population(description: str | None, location: str | None) -> SeverityFactor:
    """Factor 6: explicit vulnerable-setting/population terms in the report text."""
    text = f"{description or ''} {location or ''}".lower()
    found = []
    for term in VULNERABLE_TERMS:
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text):
            found.append(term)
    points = VULNERABLE_POPULATION_MAX_POINTS if found else 0
    reason = (
        "vulnerable population/setting mentioned: " + ", ".join(found)
        if found
        else "no hospital, school, elderly, child, infant or care-setting term recorded"
    )
    return SeverityFactor(
        factor="vulnerable_population",
        points=points,
        max_points=VULNERABLE_POPULATION_MAX_POINTS,
        reason=reason,
    )


def level_for_score(score: int) -> SeverityLevel:
    """Turn a 0-100 score into Low / Medium / High / Critical."""
    for minimum_score, level in LEVEL_THRESHOLDS:
        if score >= minimum_score:
            return level
    return SeverityLevel.LOW


def calculate_severity(
    people_affected: int,
    help_needed: list[HelpType],
    *,
    hazard_type: HazardType | str | None = None,
    description: str | None = None,
    location: str | None = None,
    reported_at: datetime | str | None = None,
    hazard_magnitude: float | None = None,
    hazard_magnitude_unit: str | None = None,
    provider_alert_level: str | None = None,
    as_of: datetime | None = None,
) -> SeverityAssessment:
    """Calculate a transparent score using six bounded prototype factors."""
    factors = [
        score_people_affected(people_affected),
        score_immediate_help(help_needed),
        score_hazard_type(hazard_type),
        score_hazard_signal(
            hazard_type,
            hazard_magnitude,
            hazard_magnitude_unit,
            provider_alert_level,
        ),
        score_event_recency(reported_at, as_of=as_of),
        score_vulnerable_population(description, location),
    ]
    score = sum(factor.points for factor in factors)
    level = level_for_score(score)
    parts = [f"{factor.reason} (+{factor.points}/{factor.max_points})" for factor in factors]
    explanation = f"Score {score}/{MAX_SCORE} ({level.value}): " + "; ".join(parts)

    return SeverityAssessment(
        score=score,
        max_score=MAX_SCORE,
        level=level,
        explanation=explanation,
        factors=factors,
        rules_version=RULES_VERSION,
        disclaimer=DISCLAIMER,
    )
