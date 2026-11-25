"""Run specialist agents against imported alerts and inspect assessment history."""

from fastapi import APIRouter, HTTPException, Query, status

from app import alert_repository, assessment_orchestrator, assessment_repository
from app.assessment_schemas import AlertAssessment, AlertAssessmentHistory

router = APIRouter(prefix="/api/alerts", tags=["Agent Assessments"])


@router.post("/{alert_id}/assessments", response_model=AlertAssessment, status_code=status.HTTP_201_CREATED)
def create_alert_assessment(alert_id: int) -> dict:
    """Run the specialist agents and persist a snapshot for human review."""
    alert = alert_repository.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External alert {alert_id} not found.",
        )

    result = assessment_orchestrator.assess_alert(alert)
    return assessment_repository.save_assessment(alert, result)


@router.get("/{alert_id}/assessments", response_model=AlertAssessmentHistory)
def list_alert_assessments(
    alert_id: int,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List immutable assessment snapshots for one external alert."""
    alert = alert_repository.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"External alert {alert_id} not found.",
        )

    assessments = assessment_repository.list_assessments_for_alert(alert_id, limit=limit)
    return {
        "alert_id": alert_id,
        "count": len(assessments),
        "assessments": assessments,
    }


@router.get("/assessments/{assessment_id}", response_model=AlertAssessment)
def get_alert_assessment(assessment_id: int) -> dict:
    assessment = assessment_repository.get_assessment_by_id(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found.",
        )
    return assessment
