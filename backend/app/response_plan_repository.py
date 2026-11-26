"""Transactional storage for simulated assignments and response-plan audit history."""

import sqlite3
from typing import Any

from app.database import get_connection
from app.schemas import utc_now
from app.response_plan_schemas import ResponsePlanDecision


class ResponsePlanConflict(RuntimeError):
    """Raised when a plan cannot transition due to state or stock conflicts."""


class ResourceReservationConflict(ResponsePlanConflict):
    """Raised when active simulations already reserve too much stock."""


def _row_to_plan(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    items = connection.execute(
        """
        SELECT rpi.id, rpi.resource_id, rpi.resource_name, rpi.resource_type,
               rpi.resource_location, rpi.assigned_quantity, rpi.distance_km,
               rpi.distance_basis, d.status AS deployment_status,
               d.incident_id AS assigned_incident_id
        FROM response_plan_items rpi
        LEFT JOIN dispatch_deployments d
          ON d.plan_id = rpi.response_plan_id AND d.resource_id = rpi.resource_id
        WHERE rpi.response_plan_id = ?
        ORDER BY rpi.id
        """,
        (row["id"],),
    ).fetchall()
    actions = connection.execute(
        """
        SELECT id, action, note, created_at
        FROM response_plan_actions
        WHERE response_plan_id = ?
        ORDER BY id
        """,
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "incident_id": row["incident_id"],
        "recommendation_id": row["recommendation_id"],
        "status": row["status"],
        "dispatch_mode": row["dispatch_mode"] if "dispatch_mode" in row.keys() else "manual",
        "summary": row["summary"],
        "decision_note": row["decision_note"],
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
        "completed_at": row["completed_at"],
        "items": [dict(item) for item in items],
        "actions": [dict(action) for action in actions],
    }


def create_response_plan(incident_id: int, recommendation) -> dict[str, Any]:
    """Create a pending plan from an approved recommendation snapshot."""
    if not recommendation.items:
        raise ResponsePlanConflict(
            "This recommendation contains no matched resources and cannot create a response plan."
        )

    created_at = utc_now().isoformat()
    summary = (
        f"Simulation plan for incident #{incident_id}: "
        f"{len(recommendation.items)} resource pool(s), "
        f"{sum(item.recommended_quantity for item in recommendation.items)} unit(s) proposed."
    )
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            INSERT INTO response_plans (
                incident_id, recommendation_id, status, summary, created_at
            )
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (incident_id, recommendation.id, summary, created_at),
        )
        plan_id = int(cursor.lastrowid)

        for item in recommendation.items:
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
            INSERT INTO response_plan_actions (response_plan_id, action, note, created_at)
            VALUES (?, 'created', 'Created from an approved resource recommendation; awaiting simulation approval.', ?)
            """,
            (plan_id, created_at),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _row_to_plan(connection, row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def get_response_plan(plan_id: int) -> dict[str, Any] | None:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _row_to_plan(connection, row) if row is not None else None
    finally:
        connection.close()


def list_response_plans(status: str | None = None) -> list[dict[str, Any]]:
    connection = get_connection()
    try:
        if status:
            rows = connection.execute(
                "SELECT * FROM response_plans WHERE status = ? ORDER BY id DESC",
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM response_plans ORDER BY id DESC"
            ).fetchall()
        return [_row_to_plan(connection, row) for row in rows]
    finally:
        connection.close()


def decide_response_plan(
    plan_id: int,
    decision: ResponsePlanDecision,
    note: str | None,
) -> dict[str, Any]:
    """Approve into simulated reservations or reject, without changing inventory."""
    connection = get_connection()
    decided_at = utc_now().isoformat()
    try:
        connection.execute("BEGIN IMMEDIATE")
        plan = connection.execute(
            "SELECT * FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if plan is None:
            raise LookupError(f"Response plan {plan_id} not found.")
        if plan["status"] != "pending":
            raise ResponsePlanConflict(
                f"Response plan {plan_id} is already {plan['status']}."
            )

        if decision == ResponsePlanDecision.APPROVE:
            items = connection.execute(
                """
                SELECT resource_id, resource_name, assigned_quantity
                FROM response_plan_items
                WHERE response_plan_id = ?
                ORDER BY id
                """,
                (plan_id,),
            ).fetchall()

            for item in items:
                resource = connection.execute(
                    """
                    SELECT quantity_available, availability_status
                    FROM resources WHERE id = ?
                    """,
                    (item["resource_id"],),
                ).fetchone()
                if resource is None or resource["availability_status"] != "available":
                    raise ResourceReservationConflict(
                        f"{item['resource_name']} is no longer marked available."
                    )

                already_reserved = connection.execute(
                    """
                    SELECT COALESCE(SUM(rpi.assigned_quantity), 0)
                    FROM response_plan_items rpi
                    JOIN response_plans rp ON rp.id = rpi.response_plan_id
                    WHERE rpi.resource_id = ?
                      AND rp.status = 'simulated'
                    """,
                    (item["resource_id"],),
                ).fetchone()[0]
                remaining = resource["quantity_available"] - int(already_reserved)
                if item["assigned_quantity"] > remaining:
                    raise ResourceReservationConflict(
                        f"{item['resource_name']} has {remaining} unreserved unit(s), "
                        f"but this plan needs {item['assigned_quantity']}."
                    )

            next_status = "simulated"
            action = "simulated"
            action_note = note or "Operator approved the plan for simulation; stock reserved in the simulation ledger only."
        else:
            next_status = "rejected"
            action = "rejected"
            action_note = note or "Operator rejected the response plan."

        connection.execute(
            """
            UPDATE response_plans
            SET status = ?, decision_note = ?, decided_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (next_status, note, decided_at, plan_id),
        )
        connection.execute(
            """
            INSERT INTO response_plan_actions (response_plan_id, action, note, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (plan_id, action, action_note, decided_at),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _row_to_plan(connection, row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def complete_response_plan(plan_id: int, note: str | None) -> dict[str, Any]:
    """Close a simulation and release its reserved quantities for later simulations."""
    completed_at = utc_now().isoformat()
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Response plan {plan_id} not found.")
        if row["status"] != "simulated":
            raise ResponsePlanConflict(
                f"Only a simulated plan can be completed (current status: {row['status']})."
            )

        connection.execute(
            """
            UPDATE response_plans
            SET status = 'completed', completed_at = ?
            WHERE id = ? AND status = 'simulated'
            """,
            (completed_at, plan_id),
        )
        connection.execute(
            """
            INSERT INTO response_plan_actions (response_plan_id, action, note, created_at)
            VALUES (?, 'completed', ?, ?)
            """,
            (
                plan_id,
                note or "Simulation marked complete; simulation-only reservations released.",
                completed_at,
            ),
        )

        connection.execute(
            """
            UPDATE dispatch_deployments
            SET status = 'completed', updated_at = ?
            WHERE plan_id = ? AND status = 'deployed'
            """,
            (completed_at, plan_id),
        )
        connection.execute(
            """
            INSERT INTO dispatch_audit_events
                (incident_id, recommendation_id, plan_id, action, actor, note, created_at)
            SELECT incident_id, recommendation_id, id, 'completed', 'operator', ?, ?
            FROM response_plans
            WHERE id = ? AND dispatch_mode = 'auto'
            """,
            (note or "Operator completed the simulated deployment.", completed_at, plan_id),
        )
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _row_to_plan(connection, updated)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()



def recall_response_plan(plan_id: int, note: str | None) -> dict[str, Any]:
    """Recall an active AUTO deployment and release its simulated reservations."""
    recalled_at = utc_now().isoformat()
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status, dispatch_mode FROM response_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Response plan {plan_id} not found.")
        if row["status"] != "simulated" or row["dispatch_mode"] != "auto":
            raise ResponsePlanConflict(
                "Only an active AUTO deployment can be recalled."
            )
        active = connection.execute(
            "SELECT COUNT(*) FROM dispatch_deployments "
            "WHERE plan_id = ? AND status = 'deployed'",
            (plan_id,),
        ).fetchone()[0]
        if int(active) == 0:
            raise ResponsePlanConflict("This plan has no active deployed assignments.")

        connection.execute(
            """
            UPDATE response_plans
            SET status = 'completed', completed_at = ?,
                decision_note = ?
            WHERE id = ? AND status = 'simulated'
            """,
            (recalled_at, note or "Operator recalled the simulated deployment.", plan_id),
        )
        connection.execute(
            """
            UPDATE dispatch_deployments
            SET status = 'recalled', updated_at = ?
            WHERE plan_id = ? AND status = 'deployed'
            """,
            (recalled_at, plan_id),
        )
        connection.execute(
            """
            INSERT INTO response_plan_actions (response_plan_id, action, note, created_at)
            VALUES (?, 'completed', ?, ?)
            """,
            (
                plan_id,
                note or "AUTO deployment recalled by operator; reservations released.",
                recalled_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO dispatch_audit_events
                (incident_id, recommendation_id, plan_id, action, actor, note, created_at)
            SELECT incident_id, recommendation_id, id, 'recalled', 'operator', ?, ?
            FROM response_plans WHERE id = ?
            """,
            (note or "Operator recalled the simulated deployment.", recalled_at, plan_id),
        )
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM response_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _row_to_plan(connection, updated)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
