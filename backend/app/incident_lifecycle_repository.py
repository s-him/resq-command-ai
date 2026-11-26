"""Transactional incident lifecycle changes and operator activity records."""

from app import incident_repository
from app.database import get_connection
from app.schemas import IncidentStatus, utc_now


class IncidentLifecycleConflict(RuntimeError):
    """Raised when an incident cannot make the requested lifecycle transition."""


def change_incident_status(
    incident_id: int,
    new_status: IncidentStatus,
    note: str | None,
) -> dict | None:
    """Apply an allowed status transition and append an audit row atomically."""
    connection = get_connection()
    changed_at = utc_now().isoformat()
    try:
        connection.execute("BEGIN IMMEDIATE")
        incident = connection.execute(
            "SELECT id, status FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
        if incident is None:
            connection.rollback()
            return None

        current = IncidentStatus(incident["status"])
        if current == new_status:
            raise IncidentLifecycleConflict(
                f"Incident is already {current.value}."
            )
        if current == IncidentStatus.CLOSED:
            raise IncidentLifecycleConflict(
                "Closed incidents are final in this prototype and cannot be reopened."
            )

        allowed = {
            IncidentStatus.OPEN: {IncidentStatus.RESOLVED},
            IncidentStatus.RESOLVED: {IncidentStatus.OPEN, IncidentStatus.CLOSED},
            IncidentStatus.CLOSED: set(),
        }
        if new_status not in allowed[current]:
            raise IncidentLifecycleConflict(
                f"Invalid transition: {current.value} → {new_status.value}. "
                "Resolve an open incident before closing it."
            )

        if new_status == IncidentStatus.CLOSED:
            active_simulations = connection.execute(
                """
                SELECT COUNT(*)
                FROM response_plans
                WHERE incident_id = ? AND status = 'simulated'
                """,
                (incident_id,),
            ).fetchone()[0]
            if active_simulations:
                raise IncidentLifecycleConflict(
                    f"Cannot close this incident while {active_simulations} "
                    "response simulation(s) are still active. Complete the "
                    "simulation plan(s) first."
                )

        if current == IncidentStatus.OPEN:
            incident_repository.save_current_severity(connection, incident_id)

        connection.execute(
            "UPDATE incidents SET status = ? WHERE id = ?",
            (new_status.value, incident_id),
        )
        cursor = connection.execute(
            """
            INSERT INTO incident_updates (
                incident_id, event_type, previous_status, new_status, note, created_at
            )
            VALUES (?, 'status_changed', ?, ?, ?, ?)
            """,
            (incident_id, current.value, new_status.value, note, changed_at),
        )
        connection.commit()
        return {
            "id": int(cursor.lastrowid),
            "incident_id": incident_id,
            "event_type": "status_changed",
            "previous_status": current.value,
            "new_status": new_status.value,
            "note": note,
            "created_at": changed_at,
        }
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def add_operator_note(incident_id: int, note: str) -> dict | None:
    """Append a timestamped operator note without changing the incident state."""
    connection = get_connection()
    created_at = utc_now().isoformat()
    try:
        connection.execute("BEGIN IMMEDIATE")
        incident = connection.execute(
            "SELECT id, status FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
        if incident is None:
            connection.rollback()
            return None
        if incident["status"] == IncidentStatus.CLOSED.value:
            raise IncidentLifecycleConflict(
                "A closed incident cannot receive new operational updates."
            )

        cursor = connection.execute(
            """
            INSERT INTO incident_updates (
                incident_id, event_type, previous_status, new_status, note, created_at
            )
            VALUES (?, 'operator_note', NULL, NULL, ?, ?)
            """,
            (incident_id, note, created_at),
        )
        connection.commit()
        return {
            "id": int(cursor.lastrowid),
            "incident_id": incident_id,
            "event_type": "operator_note",
            "previous_status": None,
            "new_status": None,
            "note": note,
            "created_at": created_at,
        }
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def list_incident_updates(incident_id: int) -> list[dict]:
    """Return the operational history in chronological order."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, incident_id, event_type, previous_status, new_status, note, created_at
            FROM incident_updates
            WHERE incident_id = ?
            ORDER BY id
            """,
            (incident_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def count_active_simulations(incident_id: int) -> int:
    connection = get_connection()
    try:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM response_plans
            WHERE incident_id = ? AND status = 'simulated'
            """,
            (incident_id,),
        ).fetchone()[0]
        return int(count)
    finally:
        connection.close()
