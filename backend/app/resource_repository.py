"""
All SQL for resources lives here.

Routers call these functions instead of writing SQL themselves. This keeps
the endpoint code short and matches how incident_repository.py is structured.
"""

import json
import sqlite3

from app.database import get_connection
from app.geo import haversine_km
from app.schemas import AvailabilityStatus, Resource, ResourceCreate, ResourceUpdate, utc_now


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
        deployed_quantity=(
            int(row["deployed_quantity"])
            if "deployed_quantity" in row_keys else 0
        ),
    )


def create_resource(data: ResourceCreate) -> Resource:
    """Save a new resource and record its creation in the audit history."""
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        created_at = utc_now().isoformat()
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
                created_at,
                data.latitude,
                data.longitude,
            ),
        )
        new_id = int(cursor.lastrowid)
        initial_changes = {
            field: {"from": None, "to": value}
            for field, value in {
                "resource_type": data.resource_type.value,
                "name": data.name,
                "quantity_available": data.quantity_available,
                "location": data.location,
                "availability_status": data.availability_status.value,
                "latitude": data.latitude,
                "longitude": data.longitude,
            }.items()
        }
        connection.execute(
            """
            INSERT INTO resource_change_history
                (resource_id, action, changes_json, note, created_at)
            VALUES (?, 'created', ?, ?, ?)
            """,
            (new_id, json.dumps(initial_changes, sort_keys=True), "Resource registered.", created_at),
        )
        connection.commit()

        row = connection.execute(
            """
            SELECT r.*,
                   COALESCE((
                       SELECT SUM(rpi.assigned_quantity)
                       FROM response_plan_items rpi
                       JOIN response_plans rp ON rp.id = rpi.response_plan_id
                       WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
                   ), 0) AS simulation_reserved_quantity,
                   COALESCE((
                       SELECT SUM(d.assigned_quantity)
                       FROM dispatch_deployments d
                       WHERE d.resource_id = r.id AND d.status = 'deployed'
                   ), 0) AS deployed_quantity
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
                   ), 0) AS simulation_reserved_quantity,
                   COALESCE((
                       SELECT SUM(d.assigned_quantity)
                       FROM dispatch_deployments d
                       WHERE d.resource_id = r.id AND d.status = 'deployed'
                   ), 0) AS deployed_quantity
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
                   ), 0) AS simulation_reserved_quantity,
                   COALESCE((
                       SELECT SUM(d.assigned_quantity)
                       FROM dispatch_deployments d
                       WHERE d.resource_id = r.id AND d.status = 'deployed'
                   ), 0) AS deployed_quantity
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
                   ), 0) AS simulation_reserved_quantity,
                   COALESCE((
                       SELECT SUM(d.assigned_quantity)
                       FROM dispatch_deployments d
                       WHERE d.resource_id = r.id AND d.status = 'deployed'
                   ), 0) AS deployed_quantity
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



class ResourceUpdateConflict(RuntimeError):
    """Raised when an inventory change would violate active simulation reservations."""


def _resource_with_reservations(connection: sqlite3.Connection, resource_id: int):
    return connection.execute(
        """
        SELECT r.*,
               COALESCE((
                   SELECT SUM(rpi.assigned_quantity)
                   FROM response_plan_items rpi
                   JOIN response_plans rp ON rp.id = rpi.response_plan_id
                   WHERE rpi.resource_id = r.id AND rp.status = 'simulated'
               ), 0) AS simulation_reserved_quantity,
               COALESCE((
                   SELECT SUM(d.assigned_quantity)
                   FROM dispatch_deployments d
                   WHERE d.resource_id = r.id AND d.status = 'deployed'
               ), 0) AS deployed_quantity
        FROM resources r
        WHERE r.id = ?
        """,
        (resource_id,),
    ).fetchone()


def update_resource(resource_id: int, data: ResourceUpdate) -> Resource | None:
    """Apply a partial inventory update and append an audit record atomically."""
    editable_fields = (
        "resource_type",
        "name",
        "quantity_available",
        "location",
        "availability_status",
        "latitude",
        "longitude",
    )
    supplied = data.model_dump(exclude_unset=True)
    note = supplied.pop("note", None)

    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _resource_with_reservations(connection, resource_id)
        if current is None:
            connection.rollback()
            return None

        reserved = int(current["simulation_reserved_quantity"])
        requested_quantity = supplied.get("quantity_available", current["quantity_available"])
        requested_status = supplied.get(
            "availability_status", current["availability_status"]
        )
        if hasattr(requested_status, "value"):
            requested_status = requested_status.value

        if requested_quantity < reserved:
            raise ResourceUpdateConflict(
                f"Cannot set physical quantity to {requested_quantity}: "
                f"{reserved} unit(s) are reserved by active simulations."
            )
        if requested_status == AvailabilityStatus.UNAVAILABLE and reserved > 0:
            raise ResourceUpdateConflict(
                f"Cannot mark this resource unavailable while {reserved} unit(s) "
                "are reserved by active simulations. Complete those simulations first."
            )

        changes: dict[str, dict] = {}
        updates: dict[str, object] = {}
        for field in editable_fields:
            if field not in supplied:
                continue
            value = supplied[field]
            if hasattr(value, "value"):
                value = value.value
            old_value = current[field]
            if old_value != value:
                updates[field] = value
                changes[field] = {"from": old_value, "to": value}

        if updates:
            assignments = ", ".join(f"{field} = ?" for field in updates)
            parameters = [*updates.values(), resource_id]
            connection.execute(
                f"UPDATE resources SET {assignments} WHERE id = ?",
                parameters,
            )
            changed_at = utc_now().isoformat()
            connection.execute(
                """
                INSERT INTO resource_change_history
                    (resource_id, action, changes_json, note, created_at)
                VALUES (?, 'updated', ?, ?, ?)
                """,
                (
                    resource_id,
                    json.dumps(changes, ensure_ascii=False, sort_keys=True),
                    note,
                    changed_at,
                ),
            )

        connection.commit()
        row = _resource_with_reservations(connection, resource_id)
        return _row_to_resource(row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def list_resource_history(resource_id: int) -> list[dict]:
    """Return the audit history for one resource, newest first."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, resource_id, action, changes_json, note, created_at
            FROM resource_change_history
            WHERE resource_id = ?
            ORDER BY id DESC
            """,
            (resource_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "resource_id": row["resource_id"],
                "action": row["action"],
                "changes": json.loads(row["changes_json"]),
                "note": row["note"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        connection.close()



def get_resource_by_id(resource_id: int) -> Resource | None:
    """Return a single resource, including simulation reservation totals."""
    connection = get_connection()
    try:
        row = _resource_with_reservations(connection, resource_id)
        return _row_to_resource(row) if row is not None else None
    finally:
        connection.close()
