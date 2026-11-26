"""Contracts for clearly labeled, synthetic demonstration scenarios."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DemoScenario(str, Enum):
    CYCLONE = "cyclone"
    FLOOD = "flood"
    EARTHQUAKE = "earthquake"


class DemoSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: DemoScenario = DemoScenario.CYCLONE


class DemoDispatchResult(BaseModel):
    incident_id: int
    attempted: bool
    dispatched: bool
    reused: bool = False
    plan_id: int | None = None
    message: str


class DemoSimulationResponse(BaseModel):
    scenario: DemoScenario
    dispatch_mode: str
    alerts_created: int = Field(ge=0)
    alerts_updated: int = Field(ge=0)
    incidents_created: int = Field(ge=0)
    resources_created: int = Field(ge=0)
    incident_ids: list[int]
    priority_order: list[int]
    agent_runs: int = Field(ge=0)
    dispatched_count: int = Field(ge=0)
    dispatch_results: list[DemoDispatchResult]
    message: str
    disclaimer: str
