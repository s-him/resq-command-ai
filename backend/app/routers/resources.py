"""
Resource register endpoints.

POST /api/resources  -> validate and save a new resource
GET  /api/resources  -> list all registered resources
"""

from fastapi import APIRouter, HTTPException, Query, status

from app import resource_repository
from app.schemas import NearbyResourceList, Resource, ResourceCreate, ResourceHistory, ResourceUpdate

router = APIRouter(prefix="/api/resources", tags=["Resources"])


@router.post("", response_model=Resource, status_code=status.HTTP_201_CREATED)
def create_resource(resource: ResourceCreate) -> Resource:
    """Register a resource in SQLite and return it with its new ID.

    By the time this function runs, FastAPI has already validated the request
    body against ResourceCreate, so `resource` is guaranteed to be valid.
    """
    return resource_repository.create_resource(resource)


@router.get("", response_model=list[Resource])
def list_resources() -> list[Resource]:
    """Return all registered resources (oldest first)."""
    return resource_repository.list_resources()




@router.get("/nearby", response_model=NearbyResourceList)
def list_nearby_resources(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=500),
) -> dict:
    """Find available, geocoded resources within a straight-line distance."""
    resources = resource_repository.list_nearby_resources(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "count": len(resources),
        "resources": resources,
        "disclaimer": (
            "Distances are straight-line estimates using the Haversine formula. "
            "They are not road distances or travel times. Only resources with "
            "registered coordinates and available positive stock are included."
        ),
    }



@router.patch("/{resource_id}", response_model=Resource)
def update_resource(resource_id: int, update: ResourceUpdate) -> Resource:
    """Update resource details while protecting active simulation reservations."""
    try:
        resource = resource_repository.update_resource(resource_id, update)
    except resource_repository.ResourceUpdateConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found.",
        )
    return resource


@router.get("/{resource_id}/history", response_model=ResourceHistory)
def get_resource_history(resource_id: int) -> dict:
    """Return the registration and inventory-change audit history for a resource."""
    resource = resource_repository.get_resource_by_id(resource_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found.",
        )
    entries = resource_repository.list_resource_history(resource_id)
    return {
        "resource_id": resource_id,
        "count": len(entries),
        "entries": entries,
    }
