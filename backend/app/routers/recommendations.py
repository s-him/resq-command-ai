"""
Recommendation review & operator decision endpoints.

GET  /api/recommendations/{recommendation_id}           -> retrieve one recommendation (with decision)
POST /api/recommendations/{recommendation_id}/decision  -> record "approved" or "rejected" + optional note
"""

from fastapi import APIRouter, HTTPException, status

from app import recommendation_repository
from app.schemas import (
    DecisionCreate,
    DecisionResult,
    Recommendation,
    RecommendationStatus,
)

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.get("/{recommendation_id}", response_model=Recommendation)
def get_recommendation(recommendation_id: int) -> Recommendation:
    """Return a single recommendation, including its decision details if reviewed."""
    recommendation = recommendation_repository.get_recommendation_by_id(recommendation_id)
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found.",
        )
    return recommendation


@router.post("/{recommendation_id}/decision", response_model=DecisionResult)
def decide_on_recommendation(
    recommendation_id: int,
    payload: DecisionCreate,
) -> DecisionResult:
    """Record an operator's "approved" or "rejected" decision on a pending recommendation.

    Saves the decision, optional note, and action-history entry. Approval rechecks
    current stock and earmarks capacity without changing physical inventory.
    """
    existing = recommendation_repository.get_recommendation_by_id(recommendation_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found.",
        )

    if existing.status != RecommendationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Recommendation {recommendation_id} has already been "
                f"{existing.status.value}."
            ),
        )

    try:
        updated, history_entry = recommendation_repository.record_decision(
            recommendation_id=existing.id,
            incident_id=existing.incident_id,
            decision=payload.decision,
            note=payload.note,
        )
    except recommendation_repository.RecommendationStockConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return DecisionResult(
        recommendation=updated,
        history_entry=history_entry,
        message=(
            f"Prototype decision '{payload.decision.value}' recorded. "
            "Physical inventory quantities were not changed. Approval earmarks the "
            "recommended capacity; approving a response plan turns that hold into a "
            "virtual reservation. Rejected or completed plans release the capacity."
        ),
    )

