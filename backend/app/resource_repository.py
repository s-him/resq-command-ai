"""
All SQL for resources lives here.

Routers call these functions instead of writing SQL themselves. This keeps
the endpoint code short and matches how incident_repository.py is structured.
"""

import sqlite3

from app.database import get_connection
from app.geo import haversine_km
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
        latitude=row["latitude"],
        longitude=row["longitude"],
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
                 availability_status, created_at, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.resource_type.value,
                data.name,
                data.quantity_available,
                data.location,
                data.availability_status.value,
                utc_now().isoformat(),
                data.latitude,
                data.longitude,
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




def list_nearby_resources(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[dict]:
    """Return available, geocoded resources within a straight-line radius."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM resources
            WHERE availability_status = ?
              AND quantity_available > 0
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """,
            (AvailabilityStatus.AVAILABLE.value,),
        ).fetchall()

        nearby = []
        for row in rows:
            resource = _row_to_resource(row)
            distance = haversine_km(
                latitude,
                longitude,
                resource.latitude,
                resource.longitude,
            )
            if distance <= radius_km:
                payload = resource.model_dump(mode="json")
                payload["distance_km"] = round(distance, 2)
                nearby.append(payload)

        nearby.sort(key=lambda item: (item["distance_km"], -item["quantity_available"], item["id"]))
        return nearby
    finally:
        connection.close()
