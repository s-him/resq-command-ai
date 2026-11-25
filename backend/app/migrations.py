"""
Versioned SQLite schema migrations.

Why this module exists:
- SQLite's `ALTER TABLE ... ADD COLUMN` can add new columns, but it cannot add
  `CHECK` or `FOREIGN KEY` constraints to tables that were created before those
  constraints existed.
- To upgrade older databases safely, we track applied migrations in a
  `schema_migrations` table, check existing rows BEFORE rebuilding any table,
  and perform table rebuilds inside a single SQLite transaction.

Safety rules:
- Existing valid rows and their IDs are always preserved.
- Invalid legacy rows are NEVER silently deleted or modified; migration stops
  with a clear DatabaseMigrationError explaining which table and row IDs need
  to be fixed first.
- Running migrations repeatedly is safe (already-applied versions are skipped).
"""

import json
import sqlite3
from datetime import datetime, timezone


class DatabaseMigrationError(RuntimeError):
    """Raised when an existing database cannot be safely migrated."""


CREATE_SCHEMA_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    applied_at  TEXT    NOT NULL
)
"""

# Target table definitions (used both for fresh databases and for rebuilding legacy tables).
TARGET_TABLE_SQL: dict[str, str] = {
    "incidents": """
        CREATE TABLE {table_name} (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            hazard_type             TEXT    NOT NULL,
            description             TEXT    NOT NULL,
            location                TEXT    NOT NULL,
            reported_at             TEXT    NOT NULL,
            people_affected         INTEGER NOT NULL CHECK (people_affected >= 0),
            help_needed             TEXT    NOT NULL,
            status                  TEXT    NOT NULL DEFAULT 'open'
                                            CHECK (status IN ('open', 'resolved', 'closed')),
            created_at              TEXT    NOT NULL,
            severity_score          INTEGER,
            severity_level          TEXT,
            severity_explanation    TEXT,
            severity_factors        TEXT,
            severity_rules_version  TEXT,
            latitude                REAL    CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
            longitude               REAL    CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),
            CHECK ((latitude IS NULL AND longitude IS NULL)
                   OR (latitude IS NOT NULL AND longitude IS NOT NULL))
        )
    """,
    "resources": """
        CREATE TABLE {table_name} (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_type       TEXT    NOT NULL,
            name                TEXT    NOT NULL,
            quantity_available  INTEGER NOT NULL CHECK (quantity_available >= 0),
            location            TEXT    NOT NULL,
            availability_status TEXT    NOT NULL
                                        CHECK (availability_status IN ('available', 'limited', 'unavailable')),
            created_at          TEXT    NOT NULL
        )
    """,
    "recommendations": """
        CREATE TABLE {table_name} (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id         INTEGER NOT NULL,
            status              TEXT    NOT NULL DEFAULT 'pending'
                                        CHECK (status IN ('pending', 'approved', 'rejected')),
            items               TEXT    NOT NULL,
            unavailable_needs   TEXT    NOT NULL,
            insufficient_needs  TEXT,
            summary             TEXT    NOT NULL,
            created_at          TEXT    NOT NULL,
            decision_note       TEXT,
            decided_at          TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents (id)
        )
    """,
    "action_history": """
        CREATE TABLE {table_name} (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id        INTEGER NOT NULL,
            recommendation_id  INTEGER NOT NULL,
            action             TEXT    NOT NULL,
            decision           TEXT    NOT NULL CHECK (decision IN ('approved', 'rejected')),
            note               TEXT,
            created_at         TEXT    NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents (id),
            FOREIGN KEY (recommendation_id) REFERENCES recommendations (id)
        )
    """,
    "recommendation_items": """
        CREATE TABLE {table_name} (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id    INTEGER NOT NULL,
            resource_id          INTEGER NOT NULL,
            recommended_quantity INTEGER NOT NULL CHECK (recommended_quantity > 0),
            available_quantity   INTEGER NOT NULL CHECK (available_quantity >= 0),
            for_help_needed      TEXT    NOT NULL,
            explanation          TEXT    NOT NULL,
            FOREIGN KEY (recommendation_id) REFERENCES recommendations (id),
            FOREIGN KEY (resource_id) REFERENCES resources (id),
            UNIQUE (recommendation_id, resource_id)
        )
    """,
}

# Ordered list of columns for each target table (used during table rebuilds).
TARGET_TABLE_COLUMNS: dict[str, list[str]] = {
    "incidents": [
        "id",
        "hazard_type",
        "description",
        "location",
        "reported_at",
        "people_affected",
        "help_needed",
        "status",
        "created_at",
        "severity_score",
        "severity_level",
        "severity_explanation",
        "severity_factors",
        "severity_rules_version",
        "latitude",
        "longitude",
    ],
    "resources": [
        "id",
        "resource_type",
        "name",
        "quantity_available",
        "location",
        "availability_status",
        "created_at",
    ],
    "recommendations": [
        "id",
        "incident_id",
        "status",
        "items",
        "unavailable_needs",
        "insufficient_needs",
        "summary",
        "created_at",
        "decision_note",
        "decided_at",
    ],
    "action_history": [
        "id",
        "incident_id",
        "recommendation_id",
        "action",
        "decision",
        "note",
        "created_at",
    ],
}

# Expected constraint snippets in sqlite_master to detect legacy tables lacking CHECKs.
REQUIRED_SCHEMA_SNIPPETS: dict[str, list[str]] = {
    "incidents": ["people_affected >= 0", "status IN ('open', 'resolved', 'closed')", "latitude >= -90"],
    "resources": ["quantity_available >= 0", "availability_status IN ('available', 'limited', 'unavailable')"],
    "recommendations": ["status IN ('pending', 'approved', 'rejected')", "FOREIGN KEY (incident_id)"],
    "action_history": ["decision IN ('approved', 'rejected')", "FOREIGN KEY (recommendation_id)"],
}

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status)",
    "CREATE INDEX IF NOT EXISTS idx_recommendations_incident_id ON recommendations (incident_id)",
    "CREATE INDEX IF NOT EXISTS idx_action_history_incident_id ON action_history (incident_id)",
    "CREATE INDEX IF NOT EXISTS idx_action_history_recommendation_id ON action_history (recommendation_id)",
]

CREATE_RECOMMENDATION_ITEM_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_recommendation_items_recommendation_id "
    "ON recommendation_items (recommendation_id)",
    "CREATE INDEX IF NOT EXISTS idx_recommendation_items_resource_id "
    "ON recommendation_items (resource_id)",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if table_name not in TARGET_TABLE_SQL:
        raise ValueError(f"Unsupported table: {table_name}")
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _table_ddl(connection: sqlite3.Connection, table_name: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row["sql"] if row and row["sql"] else ""


def _table_needs_rebuild(connection: sqlite3.Connection, table_name: str) -> bool:
    """Return True if an existing table is missing required columns or constraints."""
    existing_cols = _table_columns(connection, table_name)
    required_cols = set(TARGET_TABLE_COLUMNS[table_name])
    if not required_cols.issubset(existing_cols):
        return True

    ddl = _table_ddl(connection, table_name)
    for snippet in REQUIRED_SCHEMA_SNIPPETS[table_name]:
        if snippet not in ddl:
            return True

    return False


def _validate_legacy_data(connection: sqlite3.Connection) -> list[str]:
    """Check existing rows against the intended constraints BEFORE rebuilding tables.

    Returns a list of human-readable error strings (empty if all rows are valid).
    Never modifies or deletes any rows.
    """
    issues: list[str] = []
    tables = _existing_tables(connection)

    if "incidents" in tables:
        cols = _table_columns(connection, "incidents")
        bad_people = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM incidents WHERE people_affected IS NULL OR people_affected < 0"
            ).fetchall()
        ]
        if bad_people:
            issues.append(
                f"Table 'incidents': rows {bad_people} have negative or NULL people_affected."
            )

        bad_status = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM incidents WHERE status NOT IN ('open', 'resolved', 'closed')"
            ).fetchall()
        ]
        if bad_status:
            issues.append(
                f"Table 'incidents': rows {bad_status} have invalid status "
                "(expected 'open', 'resolved', or 'closed')."
            )

        if "latitude" in cols and "longitude" in cols:
            bad_coords = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT id FROM incidents
                    WHERE (latitude IS NULL) != (longitude IS NULL)
                       OR (latitude IS NOT NULL AND (latitude < -90 OR latitude > 90))
                       OR (longitude IS NOT NULL AND (longitude < -180 OR longitude > 180))
                    """
                ).fetchall()
            ]
            if bad_coords:
                issues.append(
                    f"Table 'incidents': rows {bad_coords} have invalid or unpaired "
                    "latitude/longitude coordinates."
                )

    if "resources" in tables:
        bad_qty = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM resources WHERE quantity_available IS NULL OR quantity_available < 0"
            ).fetchall()
        ]
        if bad_qty:
            issues.append(
                f"Table 'resources': rows {bad_qty} have negative or NULL quantity_available."
            )

        bad_avail = [
            row["id"]
            for row in connection.execute(
                """
                SELECT id FROM resources
                WHERE availability_status NOT IN ('available', 'limited', 'unavailable')
                """
            ).fetchall()
        ]
        if bad_avail:
            issues.append(
                f"Table 'resources': rows {bad_avail} have invalid availability_status "
                "(expected 'available', 'limited', or 'unavailable')."
            )

    if "recommendations" in tables:
        bad_rec_status = [
            row["id"]
            for row in connection.execute(
                """
                SELECT id FROM recommendations
                WHERE status NOT IN ('pending', 'approved', 'rejected')
                """
            ).fetchall()
        ]
        if bad_rec_status:
            issues.append(
                f"Table 'recommendations': rows {bad_rec_status} have invalid status "
                "(expected 'pending', 'approved', or 'rejected')."
            )

        if "incidents" in tables:
            orphan_recs = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT r.id FROM recommendations r
                    LEFT JOIN incidents i ON i.id = r.incident_id
                    WHERE i.id IS NULL
                    """
                ).fetchall()
            ]
            if orphan_recs:
                issues.append(
                    f"Table 'recommendations': rows {orphan_recs} reference a missing incident_id."
                )

    if "action_history" in tables:
        bad_decisions = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM action_history WHERE decision NOT IN ('approved', 'rejected')"
            ).fetchall()
        ]
        if bad_decisions:
            issues.append(
                f"Table 'action_history': rows {bad_decisions} have invalid decision "
                "(expected 'approved' or 'rejected')."
            )

        if "incidents" in tables:
            orphan_hist_inc = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT h.id FROM action_history h
                    LEFT JOIN incidents i ON i.id = h.incident_id
                    WHERE i.id IS NULL
                    """
                ).fetchall()
            ]
            if orphan_hist_inc:
                issues.append(
                    f"Table 'action_history': rows {orphan_hist_inc} reference a missing incident_id."
                )

        if "recommendations" in tables:
            orphan_hist_rec = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT h.id FROM action_history h
                    LEFT JOIN recommendations r ON r.id = h.recommendation_id
                    WHERE r.id IS NULL
                    """
                ).fetchall()
            ]
            if orphan_hist_rec:
                issues.append(
                    f"Table 'action_history': rows {orphan_hist_rec} reference a missing recommendation_id."
                )

    return issues


def _rebuild_table(connection: sqlite3.Connection, table_name: str) -> None:
    """Rebuild one existing table with the target schema, preserving all rows and IDs."""
    temp_name = f"{table_name}__migration_new"
    existing_cols = _table_columns(connection, table_name)
    target_cols = TARGET_TABLE_COLUMNS[table_name]

    select_expressions = [
        col if col in existing_cols else f"NULL AS {col}" for col in target_cols
    ]
    cols_csv = ", ".join(target_cols)
    select_csv = ", ".join(select_expressions)

    connection.execute(f"DROP TABLE IF EXISTS {temp_name}")
    connection.execute(TARGET_TABLE_SQL[table_name].format(table_name=temp_name))
    connection.execute(
        f"INSERT INTO {temp_name} ({cols_csv}) SELECT {select_csv} FROM {table_name}"
    )
    connection.execute(f"DROP TABLE {table_name}")
    connection.execute(f"ALTER TABLE {temp_name} RENAME TO {table_name}")


def _migration_001_create_missing_tables(connection: sqlite3.Connection) -> None:
    """Create any missing tables with full constraints and indexes."""
    tables = _existing_tables(connection)
    for table_name in ("incidents", "resources", "recommendations", "action_history"):
        if table_name not in tables:
            connection.execute(TARGET_TABLE_SQL[table_name].format(table_name=table_name))
    for index_sql in CREATE_INDEXES:
        connection.execute(index_sql)


def _migration_002_rebuild_legacy_tables_with_constraints(
    connection: sqlite3.Connection,
) -> None:
    """Upgrade any pre-existing tables lacking CHECK/FK constraints or new columns."""
    tables_to_rebuild = [
        name
        for name in ("incidents", "resources", "recommendations", "action_history")
        if _table_needs_rebuild(connection, name)
    ]

    if tables_to_rebuild:
        issues = _validate_legacy_data(connection)
        if issues:
            details = "\n  - ".join(issues)
            raise DatabaseMigrationError(
                "Database migration halted because existing rows violate the new "
                "schema constraints. No data was modified or deleted.\n"
                "Back up data/relief.db, fix or remove the invalid rows listed below, "
                "and restart the backend:\n"
                f"  - {details}"
            )

        for table_name in tables_to_rebuild:
            _rebuild_table(connection, table_name)

    for index_sql in CREATE_INDEXES:
        connection.execute(index_sql)

    fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        raise DatabaseMigrationError(
            f"Database migration halted: foreign key check failed on {len(fk_violations)} row(s). "
            "No changes were committed."
        )


def _migration_003_normalize_recommendation_items(
    connection: sqlite3.Connection,
) -> None:
    """Create recommendation_items and migrate existing JSON matched items safely.

    Legacy JSON in recommendations.items is preserved untouched (never dropped
    or silently altered). If any legacy item references a missing resource or
    has invalid data, migration halts with DatabaseMigrationError and rolls back.
    """
    tables = _existing_tables(connection)
    if "recommendation_items" not in tables:
        connection.execute(
            TARGET_TABLE_SQL["recommendation_items"].format(table_name="recommendation_items")
        )

    for index_sql in CREATE_RECOMMENDATION_ITEM_INDEXES:
        connection.execute(index_sql)

    existing_resource_ids = {
        row["id"] for row in connection.execute("SELECT id FROM resources").fetchall()
    }
    rec_rows = connection.execute("SELECT id, items FROM recommendations ORDER BY id").fetchall()

    issues: list[str] = []
    rows_to_insert: list[tuple] = []

    for rec_row in rec_rows:
        rec_id = rec_row["id"]
        raw_items = rec_row["items"]
        if not raw_items:
            continue

        try:
            parsed_items = json.loads(raw_items)
        except json.JSONDecodeError as exc:
            issues.append(
                f"Recommendation #{rec_id}: invalid JSON in 'items' column ({exc.msg})."
            )
            continue

        if not isinstance(parsed_items, list):
            issues.append(
                f"Recommendation #{rec_id}: 'items' column is not a JSON list."
            )
            continue

        seen_resources: set[int] = set()
        for idx, item in enumerate(parsed_items):
            if not isinstance(item, dict):
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx}: expected an object."
                )
                continue

            resource_id = item.get("resource_id")
            if not isinstance(resource_id, int) or isinstance(resource_id, bool):
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx}: missing or invalid resource_id ({resource_id!r})."
                )
                continue

            if resource_id not in existing_resource_ids:
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx}: resource_id={resource_id} "
                    "does not exist in 'resources'."
                )
                continue

            if resource_id in seen_resources:
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx}: duplicate resource_id={resource_id} "
                    "in the same recommendation."
                )
                continue
            seen_resources.add(resource_id)

            rec_qty = item.get("recommended_quantity")
            if not isinstance(rec_qty, int) or isinstance(rec_qty, bool) or rec_qty <= 0:
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx} (resource_id={resource_id}): "
                    f"recommended_quantity must be a positive integer (got {rec_qty!r})."
                )
                continue

            avail_qty = item.get("available_quantity")
            if not isinstance(avail_qty, int) or isinstance(avail_qty, bool) or avail_qty < 0:
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx} (resource_id={resource_id}): "
                    f"available_quantity must be a non-negative integer (got {avail_qty!r})."
                )
                continue

            for_help = item.get("for_help_needed", [])
            if not isinstance(for_help, list):
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx} (resource_id={resource_id}): "
                    "for_help_needed must be a list."
                )
                continue

            explanation = item.get("explanation", "")
            if not isinstance(explanation, str):
                issues.append(
                    f"Recommendation #{rec_id}, item #{idx} (resource_id={resource_id}): "
                    "explanation must be text."
                )
                continue

            rows_to_insert.append(
                (
                    rec_id,
                    resource_id,
                    rec_qty,
                    avail_qty,
                    json.dumps(for_help),
                    explanation,
                )
            )

    if issues:
        details = "\n  - ".join(issues)
        raise DatabaseMigrationError(
            "Migration 003 (normalize recommendation_items) halted because one or more "
            "legacy recommendation items cannot be safely migrated. No data was modified "
            "or discarded.\n"
            "Back up data/relief.db, fix the invalid legacy items below, and restart:\n"
            f"  - {details}"
        )

    for row_values in rows_to_insert:
        connection.execute(
            """
            INSERT OR IGNORE INTO recommendation_items
                (recommendation_id, resource_id, recommended_quantity,
                 available_quantity, for_help_needed, explanation)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            row_values,
        )

    fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        raise DatabaseMigrationError(
            f"Migration 003 halted: foreign key check failed on {len(fk_violations)} row(s). "
            "No changes were committed."
        )



def _migration_004_create_external_alert_tables(connection: sqlite3.Connection) -> None:
    """Create non-destructive tables for imported alerts and provider sync history."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS external_alerts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source              TEXT NOT NULL CHECK (source IN ('gdacs', 'usgs')),
            source_event_id     TEXT NOT NULL,
            event_type          TEXT NOT NULL,
            hazard_type         TEXT NOT NULL,
            title               TEXT NOT NULL,
            description         TEXT,
            location            TEXT,
            country             TEXT,
            alert_level         TEXT,
            alert_score         REAL,
            severity_value      REAL,
            severity_unit       TEXT,
            severity_text       TEXT,
            latitude            REAL CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
            longitude           REAL CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),
            depth_km            REAL,
            event_at            TEXT,
            source_updated_at   TEXT,
            source_url          TEXT,
            raw_data            TEXT NOT NULL,
            first_seen_at       TEXT NOT NULL,
            last_seen_at        TEXT NOT NULL,
            review_status       TEXT NOT NULL DEFAULT 'new'
                                    CHECK (review_status IN ('new', 'reviewed', 'dismissed')),
            reviewed_at         TEXT,
            review_note         TEXT,
            CHECK ((latitude IS NULL AND longitude IS NULL)
                   OR (latitude IS NOT NULL AND longitude IS NOT NULL)),
            UNIQUE (source, source_event_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_sync_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL CHECK (source IN ('gdacs', 'usgs')),
            status          TEXT NOT NULL CHECK (status IN ('success', 'failed')),
            fetched_count   INTEGER NOT NULL CHECK (fetched_count >= 0),
            created_count   INTEGER NOT NULL CHECK (created_count >= 0),
            updated_count   INTEGER NOT NULL CHECK (updated_count >= 0),
            error_message   TEXT,
            started_at      TEXT NOT NULL,
            finished_at     TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_alerts_event_at ON external_alerts (event_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_alerts_review_status ON external_alerts (review_status)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_alerts_hazard_type ON external_alerts (hazard_type)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_alert_sync_runs_source_id ON alert_sync_runs (source, id)"
    )



def _migration_005_create_alert_assessments(connection: sqlite3.Connection) -> None:
    """Create immutable snapshots from the specialist-agent assessment pipeline."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_assessments (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            external_alert_id       INTEGER NOT NULL,
            source                  TEXT NOT NULL CHECK (source IN ('gdacs', 'usgs')),
            source_event_id         TEXT NOT NULL,
            title                   TEXT NOT NULL,
            hazard_type             TEXT NOT NULL,
            engine_version          TEXT NOT NULL,
            assessment_status       TEXT NOT NULL CHECK (assessment_status = 'completed'),
            review_priority         TEXT NOT NULL CHECK (
                review_priority IN (
                    'urgent_review',
                    'priority_review',
                    'routine_review',
                    'human_interpretation_required'
                )
            ),
            human_review_required   INTEGER NOT NULL CHECK (human_review_required IN (0, 1)),
            summary                 TEXT NOT NULL,
            agents_json             TEXT NOT NULL,
            disclaimer              TEXT NOT NULL,
            generated_at            TEXT NOT NULL,
            FOREIGN KEY (external_alert_id) REFERENCES external_alerts (id) ON DELETE RESTRICT
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_alert_assessments_alert_id "
        "ON alert_assessments (external_alert_id, id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_alert_assessments_priority "
        "ON alert_assessments (review_priority, id)"
    )



def _migration_006_add_resource_coordinates_and_match_distances(
    connection: sqlite3.Connection,
) -> None:
    """Add optional coordinates to resources and distances to saved suggestions."""
    resource_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(resources)").fetchall()
    }
    if "latitude" not in resource_columns:
        connection.execute(
            "ALTER TABLE resources ADD COLUMN latitude REAL "
            "CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90))"
        )
    if "longitude" not in resource_columns:
        connection.execute(
            "ALTER TABLE resources ADD COLUMN longitude REAL "
            "CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180))"
        )

    recommendation_item_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(recommendation_items)").fetchall()
    }
    if "distance_km" not in recommendation_item_columns:
        connection.execute(
            "ALTER TABLE recommendation_items ADD COLUMN distance_km REAL "
            "CHECK (distance_km IS NULL OR distance_km >= 0)"
        )
    if "distance_basis" not in recommendation_item_columns:
        connection.execute(
            "ALTER TABLE recommendation_items ADD COLUMN distance_basis TEXT "
            "NOT NULL DEFAULT 'not_available' "
            "CHECK (distance_basis IN ('haversine_straight_line', 'not_available'))"
        )



def _migration_007_create_response_plan_simulation_tables(
    connection: sqlite3.Connection,
) -> None:
    """Create human-gated response plans, simulation reservations and audit records."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS response_plans (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id         INTEGER NOT NULL,
            recommendation_id   INTEGER NOT NULL UNIQUE,
            status              TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'simulated', 'rejected', 'completed')),
            summary             TEXT NOT NULL,
            decision_note       TEXT,
            created_at          TEXT NOT NULL,
            decided_at          TEXT,
            completed_at        TEXT,
            FOREIGN KEY (incident_id) REFERENCES incidents (id),
            FOREIGN KEY (recommendation_id) REFERENCES recommendations (id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS response_plan_items (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            response_plan_id    INTEGER NOT NULL,
            resource_id         INTEGER NOT NULL,
            resource_name       TEXT NOT NULL,
            resource_type       TEXT NOT NULL,
            resource_location   TEXT NOT NULL,
            assigned_quantity   INTEGER NOT NULL CHECK (assigned_quantity > 0),
            distance_km         REAL CHECK (distance_km IS NULL OR distance_km >= 0),
            distance_basis      TEXT NOT NULL DEFAULT 'not_available'
                                    CHECK (distance_basis IN ('haversine_straight_line', 'not_available')),
            FOREIGN KEY (response_plan_id) REFERENCES response_plans (id),
            FOREIGN KEY (resource_id) REFERENCES resources (id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS response_plan_actions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            response_plan_id    INTEGER NOT NULL,
            action              TEXT NOT NULL
                                    CHECK (action IN ('created', 'simulated', 'rejected', 'completed')),
            note                TEXT,
            created_at          TEXT NOT NULL,
            FOREIGN KEY (response_plan_id) REFERENCES response_plans (id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_response_plans_incident_id "
        "ON response_plans (incident_id, id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_response_plans_status "
        "ON response_plans (status, id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_response_plan_items_resource "
        "ON response_plan_items (resource_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_response_plan_actions_plan "
        "ON response_plan_actions (response_plan_id, id)"
    )



def _migration_008_link_reviewed_alerts_to_incidents(
    connection: sqlite3.Connection,
) -> None:
    """Add an optional one-way link from a reviewed external alert to its incident."""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(external_alerts)").fetchall()
    }
    if "linked_incident_id" not in columns:
        connection.execute(
            "ALTER TABLE external_alerts ADD COLUMN linked_incident_id "
            "INTEGER REFERENCES incidents (id)"
        )
    if "linked_at" not in columns:
        connection.execute(
            "ALTER TABLE external_alerts ADD COLUMN linked_at TEXT"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_alerts_linked_incident "
        "ON external_alerts (linked_incident_id)"
    )


MIGRATIONS: list[tuple[int, str, callable]] = [
    (1, "001_create_missing_tables", _migration_001_create_missing_tables),
    (2, "002_enforce_constraints_and_rebuild_legacy_tables", _migration_002_rebuild_legacy_tables_with_constraints),
    (3, "003_normalize_recommendation_items", _migration_003_normalize_recommendation_items),
    (4, "004_create_external_alert_tables", _migration_004_create_external_alert_tables),
    (5, "005_create_alert_assessments", _migration_005_create_alert_assessments),
    (6, "006_add_resource_coordinates_and_match_distances", _migration_006_add_resource_coordinates_and_match_distances),
    (7, "007_create_response_plan_simulation_tables", _migration_007_create_response_plan_simulation_tables),
    (8, "008_link_reviewed_alerts_to_incidents", _migration_008_link_reviewed_alerts_to_incidents),
]


def get_applied_versions(connection: sqlite3.Connection) -> set[int]:
    """Return the set of migration version numbers already recorded."""
    if "schema_migrations" not in _existing_tables(connection):
        return set()
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def run_migrations(connection: sqlite3.Connection) -> list[int]:
    """Apply any pending migrations in version order, each inside a transaction.

    Returns the list of newly applied version numbers.
    """
    # Ensure schema_migrations exists before checking versions.
    connection.execute(CREATE_SCHEMA_MIGRATIONS_TABLE)
    connection.commit()

    applied = get_applied_versions(connection)
    newly_applied: list[int] = []

    for version, name, migrate_fn in MIGRATIONS:
        if version in applied:
            continue

        # SQLite requires foreign_keys = OFF while dropping/renaming parent tables
        # during a table rebuild, then PRAGMA foreign_key_check verifies integrity
        # before COMMIT. We always restore foreign_keys = ON afterward.
        needs_fk_off = version == 2
        if needs_fk_off:
            connection.execute("PRAGMA foreign_keys = OFF")

        try:
            connection.execute("BEGIN IMMEDIATE")
            migrate_fn(connection)
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _utc_now_iso()),
            )
            connection.commit()
            newly_applied.append(version)
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")

    return newly_applied

