"""One-click synthetic demo scenario endpoint."""

from fastapi import APIRouter, HTTPException, status

from app.demo_schemas import DemoSimulationRequest, DemoSimulationResponse
from app.demo_service import run_demo_scenario

router = APIRouter(prefix="/api/demo", tags=["Demo"])


@router.post(
    "/simulate",
    response_model=DemoSimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_demo(request: DemoSimulationRequest) -> dict:
    """Inject a labeled sample scenario and run the standard advisory workflow."""
    try:
        return run_demo_scenario(request.scenario.value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
