"""Human-gated response plan and dispatch simulation endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from app import incident_repository, recommendation_repository, response_plan_repository
from app.response_plan_schemas import (
    ResponsePlan,
    ResponsePlanCompleteRequest,
    ResponsePlanCreate,
    ResponsePlanDecisionRequest,
    ResponsePlanDecisionResult,
    ResponsePlanList,
    ResponsePlanStatus,
)
from app.schemas import RecommendationStatus


DISCLAIMER = (
    "Academic dispatch simulation only. No emergency service is contacted, no vehicle "
    "or team is dispatched, and no physical stock is changed. Approved plans reserve "
    "quantities only in this prototype's simulation ledger. A human operator must "
    "verify resource availability and real-world conditions independently."
)

router = APIRouter(tags=["Response Plan Simulation"])


@router.post(
    "/api/incidents/{incident_id}/response-plans",
    response_model=ResponsePlan,
    status_code=status.HTTP_201_CREATED,
)
def create_response_plan(incident_id: int, request: ResponsePlanCreate) -> dict:
    """Create a pending simulation plan from an already-approved recommendation."""
    incident = incident_repository.get_incident_by_id(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )

    recommendation = recommendation_repository.get_recommendation_by_id(
        request.recommendation_id
    )
    if recommendation is None or recommendation.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved recommendation for this incident was not found.",
        )
    if recommendation.status != RecommendationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the resource recommendation before creating a response plan.",
        )

    try:
        return response_plan_repository.create_response_plan(incident_id, recommendation)
    except response_plan_repository.ResponsePlanConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A response plan already exists for this recommendation.",
            ) from exc
        raise


@router.get("/api/response-plans", response_model=ResponsePlanList)
def list_response_plans(
    plan_status: ResponsePlanStatus | None = Query(default=None, alias="status"),
) -> dict:
    plans = response_plan_repository.list_response_plans(
        status=plan_status.value if plan_status else None
    )
    return {"count": len(plans), "plans": plans, "disclaimer": DISCLAIMER}


@router.get("/api/response-plans/{plan_id}", response_model=ResponsePlan)
def get_response_plan(plan_id: int) -> dict:
    plan = response_plan_repository.get_response_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Response plan {plan_id} not found.",
        )
    return plan


@router.post(
    "/api/response-plans/{plan_id}/decision",
    response_model=ResponsePlanDecisionResult,
)
def decide_response_plan(plan_id: int, request: ResponsePlanDecisionRequest) -> dict:
    try:
        plan = response_plan_repository.decide_response_plan(
            plan_id=plan_id,
            decision=request.decision,
            note=request.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except response_plan_repository.ResourceReservationConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except response_plan_repository.ResponsePlanConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    message = (
        "Simulation approved. Quantities are reserved only in the simulation ledger; "
        "no real dispatch or physical stock change occurred."
        if request.decision.value == "approve"
        else "Response plan rejected. No resources were reserved."
    )
    return {"plan": plan, "message": message}


@router.post(
    "/api/response-plans/{plan_id}/complete",
    response_model=ResponsePlan,
)
def complete_response_plan(
    plan_id: int,
    request: ResponsePlanCompleteRequest,
) -> dict:
    try:
        return response_plan_repository.complete_response_plan(plan_id, request.note)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except response_plan_repository.ResponsePlanConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc



@router.post(
    "/api/response-plans/{plan_id}/recall",
    response_model=ResponsePlan,
)
def recall_response_plan(plan_id: int, request: ResponsePlanCompleteRequest) -> dict:
    """Recall an AUTO simulated deployment and release its virtual reservations."""
    try:
        return response_plan_repository.recall_response_plan(plan_id, request.note)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except response_plan_repository.ResponsePlanConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
