"""GET /api/activity -> the full action log (status changes, decisions, plans, stock)."""

from fastapi import APIRouter, Query

from app import activity_service
from app.alert_schemas import ActivityList

router = APIRouter(prefix="/api/activity", tags=["Activity History"])


@router.get("", response_model=ActivityList)
def list_activity(
    incident_id: int | None = Query(default=None, gt=0),
    alert_type: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    entries = activity_service.list_activity(
        incident_id=incident_id, alert_type=alert_type, limit=limit
    )
    return {
        "count": len(entries),
        "total_count": activity_service.count_activity(),
        "entries": entries,
    }
