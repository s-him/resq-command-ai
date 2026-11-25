"""Pydantic response contracts for traceable multi-agent assessments."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ReviewPriority(str, Enum):
    URGENT_REVIEW = "urgent_review"
    PRIORITY_REVIEW = "priority_review"
    ROUTINE_REVIEW = "routine_review"
    HUMAN_INTERPRETATION_REQUIRED = "human_interpretation_required"


class AssessmentAgentOutput(BaseModel):
    agent: str
    version: str
    status: str
    findings: dict[str, Any] | None = None


class AlertAssessment(BaseModel):
    id: int
    alert_id: int
    source: str
    source_event_id: str
    title: str
    hazard_type: str
    engine_version: str
    assessment_status: str
    review_priority: ReviewPriority
    human_review_required: bool
    summary: str
    agents: dict[str, dict[str, Any]]
    disclaimer: str
    generated_at: datetime


class AlertAssessmentHistory(BaseModel):
    alert_id: int
    count: int
    assessments: list[AlertAssessment]
