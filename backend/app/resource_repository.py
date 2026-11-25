"""
All SQL for resources lives here.

Routers call these functions instead of writing SQL themselves. This keeps
the endpoint code short and matches how incident_repository.py is structured.
"""

import sqlite3

from app.database import get_connection
from app.schemas import AvailabilityStatus, Resource, ResourceCreate, utc_now


def _row_to_resource(row: sqlite3.Row) -> Resource:
    """Convert one database row into a Resource object."""
    return Resource(
        id=row["id"],
        resource_type=row["resource_type"],
        name=row["name"],
        quantity_available=row["quantity_available"],
        location=row["location"],
        availability_status=row["availability_status"],
        created_at=row["created_at"],
    )


def create_resource(data: ResourceCreate) -> Resource:
    """Save a new resource in SQLite and return it (with its new ID)."""
    connection = get_connection()
    try:
        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            INSERT INTO resources
                (resource_type, name, quantity_available, location,
                 availability_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.resource_type.value,
                data.name,
                data.quantity_available,
                data.location,
                data.availability_status.value,
                utc_now().isoformat(),
            ),
        )
        connection.commit()
        new_id = cursor.lastrowid

        row = connection.execute("SELECT * FROM resources WHERE id = ?", (new_id,)).fetchone()
        return _row_to_resource(row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def list_resources() -> list[Resource]:
    """Return every saved resource, oldest first."""
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM resources ORDER BY id").fetchall()
        return [_row_to_resource(row) for row in rows]
    finally:
        connection.close()


def list_available_resources() -> list[Resource]:
    """Return only resources marked "available" with a positive quantity."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM resources
            WHERE availability_status = ? AND quantity_available > 0
            ORDER BY id
            """,
            (AvailabilityStatus.AVAILABLE.value,),
        ).fetchall()
        return [_row_to_resource(row) for row in rows]
    finally:
        connection.close()

