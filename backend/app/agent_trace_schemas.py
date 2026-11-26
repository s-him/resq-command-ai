"""Pydantic response models for persisted incident-agent traces."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.agent_result import AgentResult


TRACE_DISCLAIMER = (
    "Advisory academic prototype trace. Agent outputs are not verified facts or "
    "dispatch instructions. LLM output is optional and falls back to deterministic "
    "rules. No physical inventory or incident state is changed by running this pipeline."
)


class AgentTraceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    incident_id: int
    inputs_summary: dict[str, Any]
    agents: list[AgentResult]
    summary: str
    engine_version: str
    duration_ms: int = Field(ge=0)
    generated_at: str
    disclaimer: str = TRACE_DISCLAIMER


class AgentTraceList(BaseModel):
    incident_id: int
    count: int
    traces: list[AgentTraceRun]
    disclaimer: str = TRACE_DISCLAIMER
