"""Common, JSON-serializable result shape returned by every incident agent."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentResult(BaseModel):
    """One traceable agent result; output is advisory and never an instruction to dispatch."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=80)
    mode: Literal["llm", "rules"]
    output: dict[str, Any]
    rationale: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    duration_ms: int = Field(ge=0)
