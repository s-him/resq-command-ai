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
    row_keys = set(row.keys())
    reserved = int(row["simulation_reserved_quantity"]) if "simulation_reserved_quantity" in row_keys else 0
    physical = int(row["quantity_available"])
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
        simulation_reserved_quantity=reserved,
        simulation_remaining_quantity=max(0, physical - reserved),
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

        row = connection.execute(
            """
            SELECT r.*,
                   COALESCE((
                       SELECT SUM(rpi.assigned_quantity)
                       FROM response_plan_items rpi
                       JOIN response_plans rp ON rp.id = rpi.response_plan_id
                       WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
                   ), 0) AS simulation_reserved_quantity
            FROM resources r
            WHERE r.id = ?
            """,
            (new_id,),
        ).fetchone()
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
        rows = connection.execute(
            """
            SELECT r.*,
                   COALESCE((
                       SELECT SUM(rpi.assigned_quantity)
                       FROM response_plan_items rpi
                       JOIN response_plans rp ON rp.id = rpi.response_plan_id
                       WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
                   ), 0) AS simulation_reserved_quantity
            FROM resources r
            ORDER BY r.id
            """
        ).fetchall()
        return [_row_to_resource(row) for row in rows]
    finally:
        connection.close()


def list_available_resources() -> list[Resource]:
    """Return only resources marked "available" with a positive quantity."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT r.*,
                   COALESCE((
                       SELECT SUM(rpi.assigned_quantity)
                       FROM response_plan_items rpi
                       JOIN response_plans rp ON rp.id = rpi.response_plan_id
                       WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
                   ), 0) AS simulation_reserved_quantity
            FROM resources r
            WHERE r.availability_status = ? AND r.quantity_available > 0
            ORDER BY r.id
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
            SELECT r.*,
                   COALESCE((
                       SELECT SUM(rpi.assigned_quantity)
                       FROM response_plan_items rpi
                       JOIN response_plans rp ON rp.id = rpi.response_plan_id
                       WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
                   ), 0) AS simulation_reserved_quantity
            FROM resources r
            WHERE r.availability_status = ?
              AND r.quantity_available > COALESCE((
                  SELECT SUM(rpi.assigned_quantity)
                  FROM response_plan_items rpi
                  JOIN response_plans rp ON rp.id = rpi.response_plan_id
                  WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
              ), 0)
              AND r.latitude IS NOT NULL
              AND r.longitude IS NOT NULL
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
