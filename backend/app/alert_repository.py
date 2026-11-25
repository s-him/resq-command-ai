"""SQLite persistence for external disaster alerts and feed sync history."""

import json
from datetime import datetime, timezone
from typing import Any

from app.database import get_connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_alert(row) -> dict[str, Any]:
    """Return public alert fields; keep the raw provider payload internal."""
    result = dict(row)
    result.pop("raw_data", None)
    return result


def upsert_alerts(source: str, alerts: list[dict[str, Any]]) -> tuple[int, int]:
    """Insert new alerts and refresh known alerts without overwriting review decisions."""
    created_count = 0
    updated_count = 0
    now = _utc_now()
    connection = get_connection()
    try:
        connection.execute("BEGIN")
        for alert in alerts:
            existing = connection.execute(
                "SELECT id FROM external_alerts WHERE source = ? AND source_event_id = ?",
                (source, alert["source_event_id"]),
            ).fetchone()

            connection.execute(
                """
                INSERT INTO external_alerts (
                    source, source_event_id, event_type, hazard_type, title,
                    description, location, country, alert_level, alert_score,
                    severity_value, severity_unit, severity_text, latitude,
                    longitude, depth_km, event_at, source_updated_at, source_url,
                    raw_data, first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, source_event_id) DO UPDATE SET
                    event_type = excluded.event_type,
                    hazard_type = excluded.hazard_type,
                    title = excluded.title,
                    description = excluded.description,
                    location = excluded.location,
                    country = excluded.country,
                    alert_level = excluded.alert_level,
                    alert_score = excluded.alert_score,
                    severity_value = excluded.severity_value,
                    severity_unit = excluded.severity_unit,
                    severity_text = excluded.severity_text,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    depth_km = excluded.depth_km,
                    event_at = excluded.event_at,
                    source_updated_at = excluded.source_updated_at,
                    source_url = excluded.source_url,
                    raw_data = excluded.raw_data,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    source,
                    alert["source_event_id"],
                    alert["event_type"],
                    alert["hazard_type"],
                    alert["title"],
                    alert.get("description"),
                    alert.get("location"),
                    alert.get("country"),
                    alert.get("alert_level"),
                    alert.get("alert_score"),
                    alert.get("severity_value"),
                    alert.get("severity_unit"),
                    alert.get("severity_text"),
                    alert.get("latitude"),
                    alert.get("longitude"),
                    alert.get("depth_km"),
                    alert.get("event_at"),
                    alert.get("source_updated_at"),
                    alert.get("source_url"),
                    json.dumps(alert.get("raw_data", {}), ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )
            if existing is None:
                created_count += 1
            else:
                updated_count += 1

        connection.commit()
        return created_count, updated_count
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def record_sync_run(
    source: str,
    status: str,
    fetched_count: int,
    created_count: int,
    updated_count: int,
    error_message: str | None,
    started_at: str,
    finished_at: str,
) -> int:
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO alert_sync_runs (
                source, status, fetched_count, created_count, updated_count,
                error_message, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                status,
                fetched_count,
                created_count,
                updated_count,
                error_message,
                started_at,
                finished_at,
            ),
        )
        return int(cursor.lastrowid)
    finally:
        connection.close()


def latest_sync_for_source(source: str) -> dict[str, Any] | None:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT source, status, fetched_count, created_count, updated_count,
                   error_message, started_at, finished_at
            FROM alert_sync_runs
            WHERE source = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()


def list_alerts(
    source: str | None = None,
    hazard_type: str | None = None,
    alert_level: str | None = None,
    review_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return filtered alerts and the total matching count."""
    conditions: list[str] = []
    parameters: list[Any] = []
    for column, value in (
        ("source", source),
        ("hazard_type", hazard_type),
        ("alert_level", alert_level),
        ("review_status", review_status),
    ):
        if value is not None:
            conditions.append(f"{column} = ?")
            parameters.append(value)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    connection = get_connection()
    try:
        total = connection.execute(
            f"SELECT COUNT(*) FROM external_alerts {where_sql}",
            parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT * FROM external_alerts
            {where_sql}
            ORDER BY
                CASE alert_level WHEN 'red' THEN 0 WHEN 'orange' THEN 1
                                 WHEN 'green' THEN 2 ELSE 3 END,
                event_at DESC,
                id DESC
            LIMIT ? OFFSET ?
            """,
            [*parameters, limit, offset],
        ).fetchall()
        return [_row_to_alert(row) for row in rows], int(total)
    finally:
        connection.close()


def review_alert(alert_id: int, status: str, note: str | None) -> dict[str, Any] | None:
    """Record a human review decision; this never creates an incident or dispatch."""
    connection = get_connection()
    try:
        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            UPDATE external_alerts
            SET review_status = ?, reviewed_at = ?, review_note = ?
            WHERE id = ?
            """,
            (status, _utc_now(), note, alert_id),
        )
        if cursor.rowcount == 0:
            connection.rollback()
            return None
        row = connection.execute(
            "SELECT * FROM external_alerts WHERE id = ?", (alert_id,)
        ).fetchone()
        connection.commit()
        return _row_to_alert(row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()



def get_alert_by_id(alert_id: int) -> dict[str, Any] | None:
    """Return one external alert without its raw provider payload."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM external_alerts WHERE id = ?",
            (alert_id,),
        ).fetchone()
        return _row_to_alert(row) if row is not None else None
    finally:
        connection.close()



def get_alert_linked_to_incident(incident_id: int) -> dict[str, Any] | None:
    """Return the most recently linked normalized provider alert for an incident."""
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT * FROM external_alerts
            WHERE linked_incident_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        return _row_to_alert(row) if row is not None else None
    finally:
        connection.close()
