"""Assess the age of the reported event timestamp."""

from datetime import datetime, timedelta, timezone
from typing import Any


AGENT_NAME = "event_recency_agent"
AGENT_VERSION = "1.0"


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_recency(
    alert: dict[str, Any],
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    event_at = _parse_datetime(alert.get("event_at"))
    if event_at is None:
        return {
            "agent": AGENT_NAME,
            "version": AGENT_VERSION,
            "status": "insufficient_data",
            "event_age_hours": None,
            "recency_band": "unknown",
            "future_timestamp": False,
            "explanation": "A valid event timestamp was not supplied by the provider.",
        }

    age = now - event_at
    if age < -timedelta(minutes=5):
        return {
            "agent": AGENT_NAME,
            "version": AGENT_VERSION,
            "status": "warning",
            "event_age_hours": round(age.total_seconds() / 3600, 2),
            "recency_band": "future_timestamp",
            "future_timestamp": True,
            "explanation": "The event timestamp is more than five minutes in the future; verify the provider data.",
        }

    age_hours = max(0.0, age.total_seconds() / 3600)
    if age_hours < 1:
        band = "within_last_hour"
    elif age_hours < 6:
        band = "within_last_six_hours"
    elif age_hours < 24:
        band = "within_last_day"
    else:
        band = "older_than_one_day"

    return {
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "completed",
        "event_age_hours": round(age_hours, 2),
        "recency_band": band,
        "future_timestamp": False,
        "explanation": f"The provider event timestamp is approximately {age_hours:.1f} hours old.",
    }
