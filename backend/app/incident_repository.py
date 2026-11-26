"""
All SQL for incidents lives here.

Routers call these functions instead of writing SQL themselves. This keeps
the endpoint code short and makes the database logic easy to find.
"""

import json
import sqlite3

from app import severity
from app.database import get_connection
from app.schemas import (
    HelpType,
    Incident,
    IncidentCreate,
    IncidentStatus,
    SeverityAssessment,
    SeverityFactor,
    utc_now,
)


def _row_to_severity(row: sqlite3.Row) -> SeverityAssessment:
    """Rebuild the saved severity assessment from its database columns."""
    return SeverityAssessment(
        score=row["severity_score"],
        max_score=severity.MAX_SCORE,
        level=row["severity_level"],
        explanation=row["severity_explanation"],
        factors=[SeverityFactor(**factor) for factor in json.loads(row["severity_factors"])],
        rules_version=row["severity_rules_version"],
        disclaimer=severity.DISCLAIMER,
    )


def _row_to_incident(row: sqlite3.Row) -> Incident:
    """Convert one database row into an Incident object."""
    return Incident(
        id=row["id"],
        hazard_type=row["hazard_type"],
        description=row["description"],
        location=row["location"],
        reported_at=row["reported_at"],
        event_at=row["event_at"],
        people_affected=row["people_affected"],
        help_needed=json.loads(row["help_needed"]),  # JSON text -> Python list
        status=row["status"],
        created_at=row["created_at"],
        severity=_row_to_severity(row),
        latitude=row["latitude"],
        longitude=row["longitude"],
        hazard_magnitude=row["hazard_magnitude"],
        hazard_magnitude_unit=row["hazard_magnitude_unit"],
        provider_alert_level=row["provider_alert_level"],
    )


def _severity_values(assessment: SeverityAssessment) -> tuple:
    """The severity values in the order of the severity_* columns."""
    return (
        assessment.score,
        assessment.level.value,
        assessment.explanation,
        json.dumps([factor.model_dump() for factor in assessment.factors]),
        assessment.rules_version,
    )


def create_incident(data: IncidentCreate) -> Incident:
    """Score a new incident, save it with status "open", and return it (with its new ID)."""
    assessment = severity.calculate_severity(
        data.people_affected,
        data.help_needed,
        hazard_type=data.hazard_type,
        description=data.description,
        location=data.location,
        reported_at=data.event_at or data.reported_at,
        hazard_magnitude=data.hazard_magnitude,
        hazard_magnitude_unit=data.hazard_magnitude_unit,
        provider_alert_level=data.provider_alert_level,
    )

    connection = get_connection()
    try:
        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            INSERT INTO incidents
                (hazard_type, description, location, reported_at,
                 people_affected, help_needed, status, created_at,
                 event_at, severity_score, severity_level, severity_explanation,
                 severity_factors, severity_rules_version,
                 latitude, longitude, hazard_magnitude, hazard_magnitude_unit,
                 provider_alert_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.hazard_type.value,
                data.description,
                data.location,
                data.reported_at.isoformat(),
                data.people_affected,
                json.dumps([help_type.value for help_type in data.help_needed]),
                IncidentStatus.OPEN.value,
                utc_now().isoformat(),
                data.event_at.isoformat() if data.event_at else None,
                *_severity_values(assessment),
                data.latitude,
                data.longitude,
                data.hazard_magnitude,
                data.hazard_magnitude_unit,
                data.provider_alert_level,
            ),
        )
        connection.commit()
        new_id = cursor.lastrowid

        row = connection.execute("SELECT * FROM incidents WHERE id = ?", (new_id,)).fetchone()
        return _row_to_incident(row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def list_incidents() -> list[Incident]:
    """Return every saved incident, oldest first."""
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM incidents ORDER BY id").fetchall()
        return [_row_to_incident(row) for row in rows]
    finally:
        connection.close()


def get_incident_by_id(incident_id: int) -> Incident | None:
    """Return one incident by ID, or None if it does not exist."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        return _row_to_incident(row) if row is not None else None
    finally:
        connection.close()


def list_open_incidents() -> list[Incident]:
    """Return only incidents whose status is "open" (resolved/closed are left out).

    They are not sorted here; prioritization.py does the ordering.
    """
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM incidents WHERE status = ? ORDER BY id",
            (IncidentStatus.OPEN.value,),
        ).fetchall()
        return [_row_to_incident(row) for row in rows]
    finally:
        connection.close()


def fill_missing_severity() -> int:
    """Calculate and save a severity score for incidents that don't have one yet.

    This upgrades incidents saved before severity scoring existed.
    Called once when the server starts. Returns how many incidents were updated.
    """
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, hazard_type, description, location, reported_at, event_at,
                   people_affected, help_needed, hazard_magnitude,
                   hazard_magnitude_unit, provider_alert_level
            FROM incidents
            WHERE severity_score IS NULL OR severity_rules_version IS NULL OR severity_rules_version != ?
            """,
            (severity.RULES_VERSION,),
        ).fetchall()
        if not rows:
            return 0

        connection.execute("BEGIN")
        for row in rows:
            help_needed = [HelpType(value) for value in json.loads(row["help_needed"])]
            assessment = severity.calculate_severity(
                row["people_affected"],
                help_needed,
                hazard_type=row["hazard_type"],
                description=row["description"],
                location=row["location"],
                reported_at=row["event_at"] or row["reported_at"],
                hazard_magnitude=row["hazard_magnitude"],
                hazard_magnitude_unit=row["hazard_magnitude_unit"],
                provider_alert_level=row["provider_alert_level"],
            )
            connection.execute(
                """
                UPDATE incidents
                SET severity_score = ?, severity_level = ?, severity_explanation = ?,
                    severity_factors = ?, severity_rules_version = ?
                WHERE id = ?
                """,
                (*_severity_values(assessment), row["id"]),
            )

        connection.commit()
        return len(rows)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
