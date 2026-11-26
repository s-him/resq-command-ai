"""Read access to the action log and the currently active alerts."""

from app import incident_repository, recommendation_repository, response_plan_repository
from app.agents.notification_agent import NotificationAgent
from app.database import get_connection


def list_activity(
    *,
    incident_id: int | None = None,
    alert_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return action-log rows, newest first."""
    clauses, values = [], []
    if incident_id is not None:
        clauses.append("incident_id = ?")
        values.append(incident_id)
    if alert_type is not None:
        clauses.append("alert_type = ?")
        values.append(alert_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    connection = get_connection()
    try:
        rows = connection.execute(
            f"""
            SELECT id AS log_id, incident_id, resource_id, recommendation_id,
                   alert_type, message, operator_decision, note, actor,
                   created_at AS timestamp
            FROM action_log {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (*values, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def count_activity() -> int:
    connection = get_connection()
    try:
        return int(connection.execute("SELECT COUNT(*) FROM action_log").fetchone()[0])
    finally:
        connection.close()


def list_active_alerts() -> list[dict]:
    open_incidents = incident_repository.list_open_incidents()
    latest = {}
    for incident in open_incidents:
        saved = recommendation_repository.list_recommendations_for_incident(incident.id)
        if saved:
            latest[incident.id] = saved[-1]
    open_ids = {incident.id for incident in open_incidents}
    pending_plans = [
        plan for plan in response_plan_repository.list_response_plans(status="pending")
        if plan["incident_id"] in open_ids
    ]
    return NotificationAgent.build_active_alerts(open_incidents, latest, pending_plans)
