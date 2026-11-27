"""Application service for syncing and reviewing public disaster alerts."""

import logging
import threading
from datetime import datetime, timezone

from app import alert_repository, alert_sources
from app.event_hub import publish_event
from app.config import (
    ALERT_AUTO_SYNC_ENABLED,
    GDACS_SYNC_INTERVAL_SECONDS,
    USGS_SYNC_INTERVAL_SECONDS,
)


DISCLAIMER = (
    "External feed alerts are unverified decision-support inputs, not confirmed "
    "incidents or emergency instructions. Review every alert before creating an "
    "incident. This prototype does not contact responders or dispatch resources."
)

SOURCE_CATALOG = {
    "gdacs": {
        "name": "Global Disaster Alert and Coordination System",
        "hazard_types": ["earthquake", "cyclone", "flood", "volcano", "drought", "wildfire"],
        "feed_url": alert_sources.GDACS_FEED_URL,
        "update_interval": "Feed reference states updates approximately every 6 minutes",
    },
    "usgs": {
        "name": "United States Geological Survey",
        "hazard_types": ["earthquake"],
        "feed_url": alert_sources.USGS_FEED_URL,
        "update_interval": "USGS summary feeds are updated approximately every minute",
    },
}


SYNC_LOCKS = {"gdacs": threading.Lock(), "usgs": threading.Lock()}
_PROVIDER_STATUS_LOCK = threading.Lock()
_PROVIDER_STATUS = {
    source: {
        "status": "ok",
        "offline_since": None,
        "last_error": None,
        "failure_count": 0,
    }
    for source in SOURCE_CATALOG
}
logger = logging.getLogger(__name__)
MAX_RETRY_BACKOFF_SECONDS = 30 * 60


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_failed(source: str, error_message: str) -> tuple[dict, bool]:
    """Record a provider failure and report whether this begins a new outage streak."""
    now = _utc_now()
    with _PROVIDER_STATUS_LOCK:
        state = _PROVIDER_STATUS[source]
        newly_offline = state["status"] != "offline"
        if newly_offline:
            state["offline_since"] = now
        state["status"] = "offline"
        state["last_error"] = error_message[:250]
        state["failure_count"] += 1
        return dict(state), newly_offline


def _provider_recovered(source: str) -> dict:
    """Clear an outage streak after a successful provider fetch and save."""
    with _PROVIDER_STATUS_LOCK:
        _PROVIDER_STATUS[source].update(
            status="ok", offline_since=None, last_error=None, failure_count=0
        )
        return dict(_PROVIDER_STATUS[source])


def provider_status(source: str) -> dict:
    with _PROVIDER_STATUS_LOCK:
        return dict(_PROVIDER_STATUS[source])


def retry_delay_seconds(source: str, base_interval_seconds: int | None = None) -> int:
    """Exponential retry backoff, capped to keep saved data available during outages."""
    base = base_interval_seconds or (
        GDACS_SYNC_INTERVAL_SECONDS if source == "gdacs" else USGS_SYNC_INTERVAL_SECONDS
    )
    failures = provider_status(source)["failure_count"]
    if failures <= 0:
        return base
    return min(base * (2 ** min(failures - 1, 10)), MAX_RETRY_BACKOFF_SECONDS)


def reset_provider_statuses() -> None:
    """Reset in-memory health for isolated tests and fresh process startup."""
    with _PROVIDER_STATUS_LOCK:
        for state in _PROVIDER_STATUS.values():
            state.update(status="ok", offline_since=None, last_error=None, failure_count=0)


def sync_sources(sources: list[str]) -> dict:
    """Fetch each provider independently so one outage does not cancel the other."""
    results: list[dict] = []

    for source in sources:
        started_at = _utc_now()
        fetched_count = 0
        created_count = 0
        updated_count = 0
        error_message = None

        try:
            lock = SYNC_LOCKS.get(source)
            if lock is None:
                raise ValueError(f"Unsupported alert source: {source}")
            with lock:
                alerts = alert_sources.fetch_alerts(source)
                fetched_count = len(alerts)
                created_count, updated_count = alert_repository.upsert_alerts(
                    source, [alert.to_dict() for alert in alerts]
                )
            status = "success"
        except Exception as exc:
            status = "failed"
            error_message = f"{type(exc).__name__}: {exc}"[:500]
            if source in _PROVIDER_STATUS:
                health, newly_offline = _provider_failed(source, error_message)
                if newly_offline:
                    logger.warning(
                        "%s feed offline since %s; keeping saved alerts (%s)",
                        source.upper(),
                        health["offline_since"],
                        health["last_error"],
                    )
        else:
            health = _provider_recovered(source)

        finished_at = _utc_now()
        alert_repository.record_sync_run(
            source=source,
            status=status,
            fetched_count=fetched_count,
            created_count=created_count,
            updated_count=updated_count,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
        )
        results.append(
            {
                "source": source,
                "status": status,
                "fetched_count": fetched_count,
                "created_count": created_count,
                "updated_count": updated_count,
                "error_message": error_message,
                "started_at": started_at,
                "finished_at": finished_at,
                "provider_status": provider_status(source) if source in _PROVIDER_STATUS else None,
            }
        )
        if created_count or updated_count:
            publish_event(
                "alerts.updated",
                {
                    "source": source,
                    "created_count": created_count,
                    "updated_count": updated_count,
                    "status": status,
                },
            )

    successes = sum(1 for result in results if result["status"] == "success")
    if successes == len(results):
        overall_status = "success"
    elif successes == 0:
        overall_status = "failed"
    else:
        overall_status = "partial"

    return {
        "status": overall_status,
        "sources": results,
        "fetched_count": sum(item["fetched_count"] for item in results),
        "created_count": sum(item["created_count"] for item in results),
        "updated_count": sum(item["updated_count"] for item in results),
        "disclaimer": DISCLAIMER,
    }


def list_source_statuses() -> list[dict]:
    """Return provider metadata and the latest recorded sync result."""
    statuses = []
    for source, metadata in SOURCE_CATALOG.items():
        latest = alert_repository.latest_sync_for_source(source)
        configured_interval = (
            GDACS_SYNC_INTERVAL_SECONDS if source == "gdacs"
            else USGS_SYNC_INTERVAL_SECONDS
        )
        statuses.append(
            {
                "source": source,
                **metadata,
                **provider_status(source),
                "automatic_sync_enabled": ALERT_AUTO_SYNC_ENABLED,
                "configured_sync_interval_seconds": configured_interval if ALERT_AUTO_SYNC_ENABLED else None,
                "retry_after_seconds": retry_delay_seconds(source, configured_interval),
                "last_sync": latest,
            }
        )
    return statuses
