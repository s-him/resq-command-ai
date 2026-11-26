"""Shared helpers for incident agents with safe deterministic fallbacks."""

import logging
from time import perf_counter
from typing import Any

from app.agents.agent_result import AgentResult
from app.llm import LLMClient
from app.schemas import Incident

logger = logging.getLogger(__name__)


class AgentBase:
    """Base class that converts every LLM error into a deterministic fallback."""

    name = "Agent"

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client if llm_client is not None else LLMClient()

    @staticmethod
    def incident_from(context: dict[str, Any]) -> Incident:
        value = context.get("incident")
        if isinstance(value, Incident):
            return value
        return Incident.model_validate(value)

    def ask_llm(
        self,
        *,
        response_model: type,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> tuple[Any | None, str | None]:
        """Return a validated LLM model, or None plus a safe fallback reason."""
        try:
            result = self.llm_client.complete_json(
                system_prompt=system_prompt,
                user_payload=user_payload,
                response_model=response_model,
            )
            return result, None
        except Exception as exc:  # Any provider, timeout, JSON or schema failure falls back.
            logger.info("%s using rules fallback after %s", self.name, type(exc).__name__)
            return None, f"LLM unavailable or invalid ({type(exc).__name__}); deterministic rules used."

    @staticmethod
    def finish(
        *,
        name: str,
        started_at: float,
        mode: str,
        output: dict[str, Any],
        rationale: str,
        confidence: float,
    ) -> AgentResult:
        elapsed_ms = max(0, round((perf_counter() - started_at) * 1000))
        return AgentResult(
            name=name,
            mode=mode,
            output=output,
            rationale=rationale,
            confidence=confidence,
            duration_ms=elapsed_ms,
        )
