"""Strict Pydantic response contracts for optional LLM suggestions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import HazardType


class StrictAgentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DetectionSuggestion(StrictAgentSchema):
    """A draft classification only; never mutates or confirms the incident."""

    actionable_candidate: bool
    hazard_type: HazardType
    draft_description: str = Field(min_length=10, max_length=1000)
    draft_location: str = Field(min_length=2, max_length=200)
    estimated_people_at_risk: int | None = Field(default=None, ge=0, le=1_000_000)
    evidence_basis: str = Field(min_length=3, max_length=500)
    rationale: str = Field(min_length=5, max_length=1000)


class SeverityNarrative(StrictAgentSchema):
    """LLM contextual wording; deterministic score and level remain authoritative."""

    reasoning: str = Field(min_length=5, max_length=1000)
    caveats: list[str] = Field(default_factory=list, max_length=8)


class PriorityNarrative(StrictAgentSchema):
    """LLM explanation supplement; cannot change deterministic rank ordering."""

    review_reason: str = Field(min_length=5, max_length=1000)
    caveats: list[str] = Field(default_factory=list, max_length=8)


class DispatchNarrative(StrictAgentSchema):
    """Narrative supplement only; allocations are built by the deterministic matcher."""

    operational_note: str = Field(min_length=5, max_length=1000)
    cautions: list[str] = Field(default_factory=list, max_length=8)


class CoordinatorNarrative(StrictAgentSchema):
    """Final plain-language summary of already-computed, validated agent outputs."""

    summary: str = Field(min_length=5, max_length=1200)
    operator_next_step: str = Field(min_length=5, max_length=500)
    cautions: list[str] = Field(default_factory=list, max_length=10)
