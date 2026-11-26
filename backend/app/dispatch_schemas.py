"""Pydantic contracts for operator-controlled simulated dispatch mode."""

from enum import Enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DispatchMode(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"


class DispatchSeverityThreshold(str, Enum):
    HIGH = "High"
    CRITICAL = "Critical"


class DispatchSettings(BaseModel):
    mode: DispatchMode
    paused: bool
    minimum_severity: DispatchSeverityThreshold
    updated_at: datetime
    updated_by: str


class DispatchSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: DispatchMode | None = None
    paused: bool | None = None
    minimum_severity: DispatchSeverityThreshold | None = None

    @model_validator(mode="after")
    def require_an_update(self) -> "DispatchSettingsUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one dispatch setting to update.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Dispatch setting values cannot be null.")
        return self


class DispatchDeployment(BaseModel):
    id: int
    plan_id: int
    incident_id: int
    resource_id: int
    assigned_quantity: int
    status: str
    actor: str
    created_at: datetime
    updated_at: datetime | None = None
    resource_name: str | None = None
    resource_type: str | None = None
    resource_location: str | None = None


class DispatchDeploymentList(BaseModel):
    count: int
    deployments: list[DispatchDeployment]
    disclaimer: str


class DispatchAuditEvent(BaseModel):
    id: int
    incident_id: int
    recommendation_id: int | None = None
    plan_id: int | None = None
    action: str
    actor: str
    note: str | None = None
    created_at: datetime


class DispatchAuditList(BaseModel):
    count: int
    events: list[DispatchAuditEvent]
    disclaimer: str


class AutoDispatchResult(BaseModel):
    incident_id: int
    attempted: bool
    dispatched: bool
    plan_id: int | None = None
    recommendation_id: int | None = None
    shortfall_count: int = Field(default=0, ge=0)
    message: str
