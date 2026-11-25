"""Persistence for immutable, traceable specialist-agent assessment snapshots."""

import json
from typing import Any

from app.database import get_connection


def _row_to_assessment(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "alert_id": row["external_alert_id"],
        "source": row["source"],
        "source_event_id": row["source_event_id"],
        "title": row["title"],
        "hazard_type": row["hazard_type"],
        "engine_version": row["engine_version"],
        "assessment_status": row["assessment_status"],
        "review_priority": row["review_priority"],
        "human_review_required": bool(row["human_review_required"]),
        "summary": row["summary"],
        "agents": json.loads(row["agents_json"]),
        "disclaimer": row["disclaimer"],
        "generated_at": row["generated_at"],
    }


def save_assessment(alert: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO alert_assessments (
                external_alert_id, source, source_event_id, title, hazard_type,
                engine_version, assessment_status, review_priority,
                human_review_required, summary, agents_json, disclaimer, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert["id"],
                alert["source"],
                alert["source_event_id"],
                alert["title"],
                alert["hazard_type"],
                result["engine_version"],
                result["assessment_status"],
                result["review_priority"],
                1 if result["human_review_required"] else 0,
                result["summary"],
                json.dumps(result["agents"], ensure_ascii=False, sort_keys=True),
                result["disclaimer"],
                result["generated_at"],
            ),
        )
        row = connection.execute(
            "SELECT * FROM alert_assessments WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _row_to_assessment(row)
    finally:
        connection.close()


def list_assessments_for_alert(alert_id: int, limit: int = 50) -> list[dict[str, Any]]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM alert_assessments
            WHERE external_alert_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (alert_id, limit),
        ).fetchall()
        return [_row_to_assessment(row) for row in rows]
    finally:
        connection.close()


def get_assessment_by_id(assessment_id: int) -> dict[str, Any] | None:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM alert_assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        return _row_to_assessment(row) if row is not None else None
    finally:
        connection.close()
