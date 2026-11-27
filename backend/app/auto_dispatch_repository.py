"""Atomic persistence for rule-validated automatic dispatch simulations."""

import json

from app.database import get_connection
from app.schemas import utc_now


class AutoDispatchStockConflict(RuntimeError):
    """Raised when stock changed after matching and can no longer be reserved."""


def _dump_models(items):
    return [item.model_dump(mode="json") for item in items]


def create_auto_dispatch(
    *,
    incident,
    items,
    unavailable_needs,
    insufficient_needs,
    summary: str,
    allow_shortfall_retry: bool = False,
    actor: str = "system-auto",
) -> dict:
    """Persist recommendation, approval, plan, reservations and audit atomically.

    All allocations are revalidated after BEGIN IMMEDIATE. A failed revalidation
    rolls the entire attempt back; stock is never decremented below zero and no
    partial database write is left behind.
    """
    created_at = utc_now().isoformat()
    shortfall_count = len(unavailable_needs) + len(insufficient_needs)
    recommendation_summary = (
        f"{summary} AUTO mode is configured; this is a simulated deployment."
    )
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")

        settings = connection.execute(
            "SELECT mode, paused, minimum_severity FROM dispatch_settings WHERE id = 1"
        ).fetchone()
        if settings is None or settings["mode"] != "auto" or settings["paused"]:
            raise AutoDispatchStockConflict(
                "Automatic dispatch is not enabled or is currently paused."
            )

        incident_level = incident.severity.level.value
        minimum_level = settings["minimum_severity"]
        if minimum_level == "Critical" and incident_level != "Critical":
            raise AutoDispatchStockConflict(
                "Incident no longer meets the current Critical-only threshold."
            )
        if minimum_level == "High" and incident_level not in {"High", "Critical"}:
            raise AutoDispatchStockConflict(
                "Incident no longer meets the current High-or-Critical threshold."
            )

        latest_event = connection.execute(
            """
            SELECT action FROM dispatch_audit_events
            WHERE incident_id = ? ORDER BY id DESC LIMIT 1
            """,
            (incident.id,),
        ).fetchone()
        if allow_shortfall_retry:
            if latest_event is None or latest_event["action"] not in {"shortfall", "partial_shortfall"}:
                raise AutoDispatchStockConflict("No retryable shortfall remains.")
        elif latest_event is not None:
            raise AutoDispatchStockConflict("An automatic dispatch attempt already exists for this incident.")

        # Validate every requested pool against active manual and auto reservations.
        for item in items:
            resource = connection.execute(
                """
                SELECT id, name, quantity_available, availability_status
                FROM resources WHERE id = ?
                """,
                (item.resource_id,),
            ).fetchone()
            if resource is None or resource["availability_status"] != "available":
                raise AutoDispatchStockConflict(
                    f"{item.resource_name} is no longer available for dispatch."
                )
            reserved = connection.execute(
                """
                SELECT COALESCE(SUM(rpi.assigned_quantity), 0)
                FROM response_plan_items rpi
                JOIN response_plans rp ON rp.id = rpi.response_plan_id
                WHERE rpi.resource_id = ? AND rp.status = 'simulated'
                """,
                (item.resource_id,),
            ).fetchone()[0]
            remaining = max(0, int(resource["quantity_available"]) - int(reserved))
            if item.recommended_quantity > remaining:
                raise AutoDispatchStockConflict(
                    f"{resource['name']} has {remaining} unreserved unit(s), "
                    f"but this dispatch needs {item.recommended_quantity}."
                )

        unavailable_json = json.dumps(_dump_models(unavailable_needs), ensure_ascii=False)
        insufficient_json = json.dumps(_dump_models(insufficient_needs), ensure_ascii=False)
        cursor = connection.execute(
            """
            INSERT INTO recommendations
                (incident_id, status, items, unavailable_needs, insufficient_needs,
                 summary, created_at, decision_note, decided_at)
            VALUES (?, 'approved', '[]', ?, ?, ?, ?, ?, ?)
            """,
            (
                incident.id,
                unavailable_json,
                insufficient_json,
                recommendation_summary,
                created_at,
                "Automatically approved by the configured AUTO simulation policy.",
                created_at,
            ),
        )
        recommendation_id = int(cursor.lastrowid)

        for item in items:
            connection.execute(
                """
                INSERT INTO recommendation_items
                    (recommendation_id, resource_id, recommended_quantity,
                     available_quantity, for_help_needed, explanation,
                     distance_km, distance_basis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    item.resource_id,
                    item.recommended_quantity,
                    item.available_quantity,
                    json.dumps([value.value for value in item.for_help_needed]),
                    item.explanation,
                    item.distance_km,
                    item.distance_basis,
                ),
            )

        connection.execute(
            """
            INSERT INTO action_history
                (incident_id, recommendation_id, action, decision, note, created_at)
            VALUES (?, ?, 'recommendation_approved', 'approved', ?, ?)
            """,
            (
                incident.id,
                recommendation_id,
                "system-auto: recommendation approved by configured AUTO simulation policy.",
                created_at,
            ),
        )

        plan_id = None
        if items:
            total_units = sum(item.recommended_quantity for item in items)
            summary_text = (
                f"AUTO simulation for incident #{incident.id}: "
                f"{len(items)} resource pool(s), {total_units} unit(s) assigned."
            )
            if shortfall_count:
                summary_text += f" Partial coverage: {shortfall_count} need(s) remain short."
            plan_cursor = connection.execute(
                """
                INSERT INTO response_plans
                    (incident_id, recommendation_id, status, summary, created_at,
                     decided_at, decision_note, dispatch_mode)
                VALUES (?, ?, 'simulated', ?, ?, ?, ?, 'auto')
                """,
                (
                    incident.id,
                    recommendation_id,
                    summary_text,
                    created_at,
                    created_at,
                    "AUTO simulation approved by system-auto; no external dispatch occurred.",
                ),
            )
            plan_id = int(plan_cursor.lastrowid)

            connection.execute(
                """
                INSERT INTO response_plan_actions
                    (response_plan_id, action, note, created_at)
                VALUES (?, 'created', ?, ?)
                """,
                (
                    plan_id,
                    "Created automatically by the configured AUTO dispatch policy.",
                    created_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO response_plan_actions
                    (response_plan_id, action, note, created_at)
                VALUES (?, 'simulated', ?, ?)
                """,
                (
                    plan_id,
                    "AUTO simulated deployment: assignments reserved transactionally; no real teams or vehicles were dispatched.",
                    created_at,
                ),
            )

            for item in items:
                connection.execute(
                    """
                    INSERT INTO response_plan_items (
                        response_plan_id, resource_id, resource_name, resource_type,
                        resource_location, assigned_quantity, distance_km, distance_basis
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        item.resource_id,
                        item.resource_name,
                        item.resource_type.value,
                        item.resource_location,
                        item.recommended_quantity,
                        item.distance_km,
                        item.distance_basis,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO dispatch_deployments (
                        plan_id, incident_id, resource_id, assigned_quantity,
                        status, actor, created_at
                    )
                    VALUES (?, ?, ?, ?, 'deployed', ?, ?)
                    """,
                    (
                        plan_id,
                        incident.id,
                        item.resource_id,
                        item.recommended_quantity,
                        actor,
                        created_at,
                    ),
                )

        action = (
            "shortfall" if not items
            else "partial_shortfall" if shortfall_count
            else "auto_dispatched"
        )
        note = (
            f"{shortfall_count} resource need(s) remain unfilled."
            if shortfall_count
            else f"{sum(item.recommended_quantity for item in items)} unit(s) assigned in the simulation ledger."
        )
        connection.execute(
            """
            INSERT INTO dispatch_audit_events
                (incident_id, recommendation_id, plan_id, action, actor, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (incident.id, recommendation_id, plan_id, action, actor, note, created_at),
        )

        connection.commit()
        return {
            "incident_id": incident.id,
            "attempted": True,
            "dispatched": bool(items),
            "plan_id": plan_id,
            "recommendation_id": recommendation_id,
            "shortfall_count": shortfall_count,
            "action": action,
            "message": (
                "AUTO simulation created a deployment assignment."
                if items
                else "AUTO simulation recorded a shortfall; no stock was assigned."
            ),
        }
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def has_auto_dispatch_history(incident_id: int) -> bool:
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT 1 FROM dispatch_audit_events WHERE incident_id = ? LIMIT 1",
            (incident_id,),
        ).fetchone() is not None
    finally:
        connection.close()


def list_shortfall_incident_ids() -> list[int]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT i.id
            FROM incidents i
            JOIN dispatch_audit_events e ON e.incident_id = i.id
            WHERE i.status = 'open'
              AND e.action IN ('shortfall', 'partial_shortfall')
              AND e.id = (
                  SELECT MAX(latest.id)
                  FROM dispatch_audit_events latest
                  WHERE latest.incident_id = i.id
              )
            ORDER BY i.severity_score DESC, i.people_affected DESC, i.reported_at, i.id
            """
        ).fetchall()
        return [int(row["id"]) for row in rows]
    finally:
        connection.close()


def get_active_deployed_quantities(incident_id: int) -> dict[str, int]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT r.resource_type, COALESCE(SUM(d.assigned_quantity), 0) AS quantity
            FROM dispatch_deployments d
            JOIN resources r ON r.id = d.resource_id
            WHERE d.incident_id = ? AND d.status = 'deployed'
            GROUP BY r.resource_type
            """,
            (incident_id,),
        ).fetchall()
        return {row["resource_type"]: int(row["quantity"]) for row in rows}
    finally:
        connection.close()


def list_deployments(status: str | None = None) -> list[dict]:
    connection = get_connection()
    try:
        where = "WHERE d.status = ?" if status else ""
        parameters = (status,) if status else ()
        rows = connection.execute(
            f"""
            SELECT d.*, r.name AS resource_name, r.resource_type,
                   r.location AS resource_location
            FROM dispatch_deployments d
            JOIN resources r ON r.id = d.resource_id
            {where}
            ORDER BY d.id DESC
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_audit_events(incident_id: int | None = None) -> list[dict]:
    connection = get_connection()
    try:
        if incident_id is None:
            rows = connection.execute(
                "SELECT * FROM dispatch_audit_events ORDER BY id DESC"
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM dispatch_audit_events WHERE incident_id = ? ORDER BY id DESC",
                (incident_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def record_dispatch_lifecycle_event(
    *, incident_id: int, plan_id: int, action: str, actor: str, note: str
) -> None:
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO dispatch_audit_events
                (incident_id, recommendation_id, plan_id, action, actor, note, created_at)
            SELECT incident_id, recommendation_id, id, ?, ?, ?, ?
            FROM response_plans WHERE id = ?
            """,
            (action, actor, note, utc_now().isoformat(), plan_id),
        )
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()



def latest_audit_event(incident_id: int) -> dict | None:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT * FROM dispatch_audit_events
            WHERE incident_id = ? ORDER BY id DESC LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()
