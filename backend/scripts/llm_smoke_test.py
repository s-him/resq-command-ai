#!/usr/bin/env python3
"""Run one clearly labeled synthetic incident through the optional LLM agents.

Run from the repository root with the backend virtual environment:
    LLM_ENABLED=true LLM_API_KEY=... backend/.venv/bin/python backend/scripts/llm_smoke_test.py

No key is read from a file or written to the database. When LLM mode is disabled
or no key is configured, the script exits without creating a smoke-test incident.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import incident_repository  # noqa: E402
from app.agent_orchestrator import run_incident_pipeline  # noqa: E402
from app.config import get_llm_settings  # noqa: E402
from app.schemas import HazardType, HelpType, IncidentCreate  # noqa: E402


def create_smoke_incident() -> Any:
    """Persist one labeled synthetic flood report for the smoke-test run."""
    now = datetime.now(timezone.utc)
    incident = IncidentCreate(
        hazard_type=HazardType.FLOOD,
        description=(
            "SIMULATED LLM smoke-test flood report near a district clinic; "
            "medical assistance and evacuation are requested."
        ),
        location="SIMULATED · LLM smoke-test district",
        reported_at=now - timedelta(minutes=2),
        event_at=now - timedelta(minutes=2),
        people_affected=120,
        help_needed=[HelpType.MEDICAL, HelpType.EVACUATION, HelpType.SHELTER],
        vulnerable_groups=[],
    )
    return incident_repository.create_incident(incident)


def run_smoke_test(
    settings: dict[str, Any] | None = None,
    *,
    incident_creator: Callable[[], Any] = create_smoke_incident,
    pipeline_runner: Callable[[int], dict[str, Any]] = run_incident_pipeline,
    output: Callable[[str], None] = print,
) -> int:
    """Return 0 for success or safe skip; return 1 when the provider test fails."""
    runtime = settings if settings is not None else get_llm_settings()

    if not runtime.get("enabled", False):
        output("LLM smoke test skipped: LLM_ENABLED is false; rules-only mode remains active.")
        return 0

    if not str(runtime.get("api_key", "")).strip():
        output("LLM smoke test skipped: LLM_ENABLED is true but LLM_API_KEY is not set.")
        return 0

    try:
        incident = incident_creator()
        output(f"Created SIMULATED smoke-test incident #{incident.id}.")
        trace = pipeline_runner(incident.id)
    except Exception as exc:
        output(
            "LLM smoke test failed safely: "
            f"{type(exc).__name__}. Check provider configuration and local database."
        )
        return 1

    agents = trace.get("agents") or []
    if not agents:
        output("LLM smoke test failed: the incident pipeline returned no agent results.")
        return 1

    llm_count = 0
    for agent in agents:
        mode = str(agent.get("mode") or "unknown")
        rationale = str(agent.get("rationale") or "No rationale was recorded.")
        output(f"{agent.get('name', 'Unknown agent')}: mode={mode}")
        output(f"  Rationale: {rationale}")
        if mode == "llm":
            llm_count += 1

    if llm_count == len(agents):
        output(f"LLM smoke test passed: all {len(agents)} agents used the configured provider.")
        return 0
    if llm_count:
        output(
            f"LLM smoke test partially failed: {llm_count}/{len(agents)} agents used the "
            "provider; remaining agents fell back to deterministic rules."
        )
    else:
        output(
            "LLM smoke test failed: all agents used deterministic rules fallback. "
            "Check provider reachability, model support and key permissions."
        )
    return 1


def main() -> int:
    return run_smoke_test()


if __name__ == "__main__":
    raise SystemExit(main())
