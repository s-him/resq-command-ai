"""
All SQL for recommendations, normalized recommendation_items, and operator
action history lives here.

Each recommendation is saved in SQLite linked to its incident_id with a
creation time and initial status "pending". Matched resource items are stored
in the relational `recommendation_items` table with foreign keys to both
`recommendations` and `resources`. Recording a decision updates the
recommendation's status/note/decided_at and writes an action_history row,
without changing any resource quantities.
"""

import json
import sqlite3

from app import recommendations
from app.database import get_connection
from app.schemas import (
    ActionHistoryEntry,
    InsufficientNeed,
    OperatorDecision,
    Recommendation,
    RecommendationStatus,
    RecommendedResourceItem,
    UnavailableNeed,
    utc_now,
)


def _load_items_for_recommendation(
    connection: sqlite3.Connection,
    recommendation_id: int,
) -> list[RecommendedResourceItem]:
    """Reconstruct matched resource items by joining recommendation_items with resources."""
    rows = connection.execute(
        """
        SELECT
            ri.resource_id,
            r.name        AS resource_name,
            r.resource_type,
            r.location    AS resource_location,
            ri.recommended_quantity,
            ri.available_quantity,
            ri.for_help_needed,
            ri.explanation,
            ri.distance_km,
            ri.distance_basis
        FROM recommendation_items ri
        JOIN resources r ON r.id = ri.resource_id
        WHERE ri.recommendation_id = ?
        ORDER BY ri.id
        """,
        (recommendation_id,),
    ).fetchall()

    return [
        RecommendedResourceItem(
            resource_id=row["resource_id"],
            resource_name=row["resource_name"],
            resource_type=row["resource_type"],
            resource_location=row["resource_location"],
            recommended_quantity=row["recommended_quantity"],
            available_quantity=row["available_quantity"],
            for_help_needed=json.loads(row["for_help_needed"]),
            explanation=row["explanation"],
            distance_km=row["distance_km"],
            distance_basis=row["distance_basis"],
        )
        for row in rows
    ]


def _row_to_recommendation(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> Recommendation:
    """Convert a recommendations row + its relational recommendation_items into Recommendation."""
    items = _load_items_for_recommendation(connection, row["id"])
    unavailable = [UnavailableNeed(**need) for need in json.loads(row["unavailable_needs"])]
    raw_insufficient = row["insufficient_needs"]
    insufficient = (
        [InsufficientNeed(**need) for need in json.loads(raw_insufficient)]
        if raw_insufficient
        else []
    )
    return Recommendation(
        id=row["id"],
        incident_id=row["incident_id"],
        status=row["status"],
        items=items,
        unavailable_needs=unavailable,
        insufficient_needs=insufficient,
        summary=row["summary"],
        disclaimer=recommendations.DISCLAIMER,
        created_at=row["created_at"],
        decision_note=row["decision_note"],
        decided_at=row["decided_at"],
    )


def _row_to_history_entry(row: sqlite3.Row) -> ActionHistoryEntry:
    """Convert one action_history row into an ActionHistoryEntry object."""
    return ActionHistoryEntry(
        id=row["id"],
        incident_id=row["incident_id"],
        recommendation_id=row["recommendation_id"],
        action=row["action"],
        decision=row["decision"],
        note=row["note"],
        created_at=row["created_at"],
    )


def create_recommendation(
    incident_id: int,
    items: list[RecommendedResourceItem],
    unavailable_needs: list[UnavailableNeed],
    insufficient_needs: list[InsufficientNeed],
    summary: str,
) -> Recommendation:
    """Save a pending recommendation and its relational recommendation_items in one transaction."""
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            INSERT INTO recommendations
                (incident_id, status, items, unavailable_needs, insufficient_needs,
                 summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                RecommendationStatus.PENDING.value,
                "[]",  # matched items now live in the relational recommendation_items table
                json.dumps([need.model_dump(mode="json") for need in unavailable_needs]),
                json.dumps([need.model_dump(mode="json") for need in insufficient_needs]),
                summary,
                utc_now().isoformat(),
            ),
        )
        new_id = cursor.lastrowid

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
                    new_id,
                    item.resource_id,
                    item.recommended_quantity,
                    item.available_quantity,
                    json.dumps([help_type.value for help_type in item.for_help_needed]),
                    item.explanation,
                    item.distance_km,
                    item.distance_basis,
                ),
            )

        connection.commit()

        row = connection.execute(
            "SELECT * FROM recommendations WHERE id = ?", (new_id,)
        ).fetchone()
        return _row_to_recommendation(connection, row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def get_recommendation_by_id(recommendation_id: int) -> Recommendation | None:
    """Return one recommendation by ID, or None if it does not exist."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)
        ).fetchone()
        return _row_to_recommendation(connection, row) if row is not None else None
    finally:
        connection.close()


def list_recommendations_for_incident(incident_id: int) -> list[Recommendation]:
    """Return every saved recommendation for a given incident, oldest first."""
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM recommendations WHERE incident_id = ? ORDER BY id",
            (incident_id,),
        ).fetchall()
        return [_row_to_recommendation(connection, row) for row in rows]
    finally:
        connection.close()


def record_decision(
    recommendation_id: int,
    incident_id: int,
    decision: OperatorDecision,
    note: str | None,
) -> tuple[Recommendation, ActionHistoryEntry]:
    """Save an operator's approve/reject decision and add an action_history row.

    Does NOT modify resource quantities.
    """
    decided_at = utc_now().isoformat()
    action = f"recommendation_{decision.value}"

    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        update_cursor = connection.execute(
            """
            UPDATE recommendations
            SET status = ?, decision_note = ?, decided_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                decision.value,
                note,
                decided_at,
                recommendation_id,
                RecommendationStatus.PENDING.value,
            ),
        )
        if update_cursor.rowcount != 1:
            raise sqlite3.IntegrityError(
                f"Recommendation {recommendation_id} is no longer pending."
            )

        history_cursor = connection.execute(
            """
            INSERT INTO action_history
                (incident_id, recommendation_id, action, decision, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (incident_id, recommendation_id, action, decision.value, note, decided_at),
        )
        connection.commit()

        rec_row = connection.execute(
            "SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)
        ).fetchone()
        history_row = connection.execute(
            "SELECT * FROM action_history WHERE id = ?", (history_cursor.lastrowid,)
        ).fetchone()
        return _row_to_recommendation(connection, rec_row), _row_to_history_entry(history_row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def list_action_history_for_incident(incident_id: int) -> list[ActionHistoryEntry]:
    """Return all recorded operator actions for an incident, oldest first."""
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM action_history WHERE incident_id = ? ORDER BY id",
            (incident_id,),
        ).fetchall()
        return [_row_to_history_entry(row) for row in rows]
    finally:
        connection.close()
