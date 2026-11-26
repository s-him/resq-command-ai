"""Contracts for human-approved response-plan and dispatch simulation workflows."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResponsePlanStatus(str, Enum):
    PENDING = "pending"
    SIMULATED = "simulated"
    REJECTED = "rejected"
    COMPLETED = "completed"


class ResponsePlanDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ResponsePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: int = Field(gt=0)


class ResponsePlanDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: ResponsePlanDecision
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def blank_note_becomes_none(cls, value: str | None) -> str | None:
        return value or None


class ResponsePlanCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def blank_note_becomes_none(cls, value: str | None) -> str | None:
        return value or None


class ResponsePlanItem(BaseModel):
    id: int
    resource_id: int
    resource_name: str
    resource_type: str
    resource_location: str
    assigned_quantity: int
    distance_km: float | None = None
    distance_basis: str
    deployment_status: str | None = None
    assigned_incident_id: int | None = None


class ResponsePlanAction(BaseModel):
    id: int
    action: str
    note: str | None = None
    created_at: datetime


class ResponsePlan(BaseModel):
    id: int
    incident_id: int
    recommendation_id: int
    status: ResponsePlanStatus
    dispatch_mode: str = "manual"
    summary: str
    decision_note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[ResponsePlanItem]
    actions: list[ResponsePlanAction]


class ResponsePlanList(BaseModel):
    count: int
    plans: list[ResponsePlan]
    disclaimer: str


class ResponsePlanDecisionResult(BaseModel):
    plan: ResponsePlan
    message: str
