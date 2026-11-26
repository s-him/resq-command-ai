"""Persistent operator settings for MANUAL/AUTO dispatch simulation."""

from app.database import get_connection
from app.schemas import utc_now


def get_dispatch_settings() -> dict:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT mode, paused, minimum_severity, updated_at, updated_by "
            "FROM dispatch_settings WHERE id = 1"
        ).fetchone()
        if row is None:
            # Migration 013 normally inserts this singleton. Keep a safe fallback
            # in case an older test database is inspected before app startup.
            return {
                "mode": "manual",
                "paused": False,
                "minimum_severity": "High",
                "updated_at": utc_now(),
                "updated_by": "system-default",
            }
        return {
            "mode": row["mode"],
            "paused": bool(row["paused"]),
            "minimum_severity": row["minimum_severity"],
            "updated_at": row["updated_at"],
            "updated_by": row["updated_by"],
        }
    finally:
        connection.close()


def update_dispatch_settings(data, *, actor: str = "operator") -> dict:
    supplied = data.model_dump(exclude_unset=True)
    if not supplied:
        raise ValueError("Provide at least one dispatch setting to update.")

    allowed = {"mode", "paused", "minimum_severity"}
    if set(supplied) - allowed:
        raise ValueError("Unsupported dispatch setting.")

    values = {}
    for key, value in supplied.items():
        values[key] = value.value if hasattr(value, "value") else value
    updated_at = utc_now().isoformat()

    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT mode, paused, minimum_severity FROM dispatch_settings WHERE id = 1"
        ).fetchone()
        if current is None:
            raise RuntimeError("Dispatch settings row is missing; run database migrations.")
        next_mode = values.get("mode", current["mode"])
        next_paused = values.get("paused", bool(current["paused"]))
        next_threshold = values.get("minimum_severity", current["minimum_severity"])
        connection.execute(
            """
            UPDATE dispatch_settings
            SET mode = ?, paused = ?, minimum_severity = ?, updated_at = ?, updated_by = ?
            WHERE id = 1
            """,
            (next_mode, int(bool(next_paused)), next_threshold, updated_at, actor),
        )
        connection.commit()
        return get_dispatch_settings()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
