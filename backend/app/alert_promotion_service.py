"""Human-reviewed external-alert promotion into the incident workflow.

Promotion is atomic: the alert must already be marked reviewed, exactly one
incident is created, and the external alert is linked to that incident in the
same SQLite transaction. No response plan or dispatch is created.
"""

import json

from app import severity
from app.database import get_connection
from app.schemas import IncidentCreate, IncidentStatus, utc_now


class AlertPromotionConflict(RuntimeError):
    """Raised when an alert cannot be promoted in its current state."""


class AlertNotReviewed(AlertPromotionConflict):
    """Only alerts explicitly marked reviewed may become incidents."""


class AlertAlreadyPromoted(AlertPromotionConflict):
    """Each external alert may create at most one incident."""


def promote_alert_to_incident(alert_id: int, data: IncidentCreate) -> int:
    """Create an incident and link the reviewed alert inside one transaction."""
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        alert = connection.execute(
            """
            SELECT id, review_status, linked_incident_id,
                   alert_level, severity_value, severity_unit, event_at
            FROM external_alerts
            WHERE id = ?
            """,
            (alert_id,),
        ).fetchone()

        if alert is None:
            raise LookupError(f"External alert {alert_id} not found.")
        if alert["linked_incident_id"] is not None:
            raise AlertAlreadyPromoted(
                f"External alert {alert_id} is already linked to incident "
                f"#{alert['linked_incident_id']}."
            )
        if alert["review_status"] != "reviewed":
            raise AlertNotReviewed(
                "Mark the external alert as reviewed before creating an incident."
            )

        magnitude = (
            data.hazard_magnitude
            if data.hazard_magnitude is not None
            else alert["severity_value"]
        )
        magnitude_unit = (
            data.hazard_magnitude_unit
            if data.hazard_magnitude_unit is not None
            else alert["severity_unit"]
        )
        provider_level = data.provider_alert_level or alert["alert_level"]
        provider_level = str(provider_level).strip().lower() if provider_level else None
        if provider_level not in {"red", "orange", "green"}:
            provider_level = None
        event_at = data.event_at or alert["event_at"]
        assessment = severity.calculate_severity(
            data.people_affected,
            data.help_needed,
            hazard_type=data.hazard_type,
            description=data.description,
            location=data.location,
            reported_at=event_at or data.reported_at,
            hazard_magnitude=magnitude,
            hazard_magnitude_unit=magnitude_unit,
            provider_alert_level=provider_level,
        )
        severity_factors = json.dumps(
            [factor.model_dump() for factor in assessment.factors]
        )
        cursor = connection.execute(
            """
            INSERT INTO incidents (
                hazard_type, description, location, reported_at,
                people_affected, help_needed, status, created_at, event_at,
                severity_score, severity_level, severity_explanation,
                severity_factors, severity_rules_version, latitude, longitude,
                hazard_magnitude, hazard_magnitude_unit, provider_alert_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.hazard_type.value,
                data.description,
                data.location,
                data.reported_at.isoformat(),
                data.people_affected,
                json.dumps([item.value for item in data.help_needed]),
                IncidentStatus.OPEN.value,
                utc_now().isoformat(),
                event_at,
                assessment.score,
                assessment.level.value,
                assessment.explanation,
                severity_factors,
                assessment.rules_version,
                data.latitude,
                data.longitude,
                magnitude,
                magnitude_unit,
                provider_level,
            ),
        )
        incident_id = int(cursor.lastrowid)
        linked_at = utc_now().isoformat()
        updated = connection.execute(
            """
            UPDATE external_alerts
            SET linked_incident_id = ?, linked_at = ?
            WHERE id = ?
              AND review_status = 'reviewed'
              AND linked_incident_id IS NULL
            """,
            (incident_id, linked_at, alert_id),
        )
        if updated.rowcount != 1:
            raise AlertPromotionConflict(
                "The alert changed while it was being promoted. Refresh and review it again."
            )

        connection.commit()
        return incident_id
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
