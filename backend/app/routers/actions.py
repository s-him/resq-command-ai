"""The decision path listed in the project synopsis."""

from fastapi import APIRouter

from app.routers.recommendations import decide_on_recommendation
from app.schemas import DecisionCreate, DecisionResult

router = APIRouter(prefix="/api/actions", tags=["Recommendations"])


@router.post("/{action_id}/decision", response_model=DecisionResult)
def decide_on_action(action_id: int, payload: DecisionCreate) -> DecisionResult:
    """Alias for /api/recommendations/{id}/decision; action_id is the recommendation ID."""
    return decide_on_recommendation(action_id, payload)
