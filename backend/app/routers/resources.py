"""
Resource register endpoints.

POST /api/resources  -> validate and save a new resource
GET  /api/resources  -> list all registered resources
"""

from fastapi import APIRouter, Query, status

from app import resource_repository
from app.schemas import NearbyResourceList, Resource, ResourceCreate

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
