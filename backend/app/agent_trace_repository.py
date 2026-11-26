"""SQLite persistence for immutable incident-agent run snapshots."""

import json
import sqlite3
from typing import Any

from app.agents.agent_result import AgentResult
from app.database import get_connection
from app.schemas import utc_now


def _row_to_trace(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "incident_id": row["incident_id"],
        "inputs_summary": json.loads(row["inputs_summary"]),
        "agents": json.loads(row["agents_json"]),
        "summary": row["summary"],
        "engine_version": row["engine_version"],
        "duration_ms": row["duration_ms"],
        "generated_at": row["generated_at"],
    }


def save_agent_trace(
    *,
    incident_id: int,
    inputs_summary: dict[str, Any],
    agents: list[AgentResult],
    summary: str,
    engine_version: str,
    duration_ms: int,
) -> dict[str, Any]:
    """Insert one immutable trace row and return the stored snapshot."""
    generated_at = utc_now().isoformat()
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            INSERT INTO incident_agent_runs
                (incident_id, inputs_summary, agents_json, summary,
                 engine_version, duration_ms, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                json.dumps(inputs_summary, ensure_ascii=False, sort_keys=True),
                json.dumps([agent.model_dump(mode="json") for agent in agents], ensure_ascii=False),
                summary,
                engine_version,
                duration_ms,
                generated_at,
            ),
        )
        run_id = int(cursor.lastrowid)
        row = connection.execute(
            "SELECT * FROM incident_agent_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        connection.commit()
        return _row_to_trace(row)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def list_agent_traces(incident_id: int, limit: int = 20) -> list[dict[str, Any]]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM incident_agent_runs
            WHERE incident_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (incident_id, limit),
        ).fetchall()
        return [_row_to_trace(row) for row in rows]
    finally:
        connection.close()
