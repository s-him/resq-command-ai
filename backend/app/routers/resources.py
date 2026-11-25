"""
Resource register endpoints.

POST /api/resources  -> validate and save a new resource
GET  /api/resources  -> list all registered resources
"""

from fastapi import APIRouter, status

from app import resource_repository
from app.schemas import Resource, ResourceCreate

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

